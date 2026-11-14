"""Qubital's two-candidate QUBO and one-layer ideal QAOA core.

No scoring or classical solver is reimplemented here. Algebraic construction is
independent of scoring.py so it can be checked against that authoritative module.
The cost operator excludes its constant; every reported expectation adds it back.
"""

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from importlib.metadata import version
from math import isfinite
from numbers import Integral, Real

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.providers.basic_provider import BasicSimulator
from qiskit.quantum_info import SparsePauliOp, Statevector
from scipy.optimize import minimize


def _finite_number(value, name):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a finite number")
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")
    return float(value)


def _positive_integer(value, name):
    if isinstance(value, bool) or not isinstance(value, Integral) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return int(value)


def _bits(canonical_bits, width):
    if not isinstance(canonical_bits, str):
        raise TypeError("canonical_bits must be a string")
    if len(canonical_bits) != width or any(b not in "01" for b in canonical_bits):
        raise ValueError(f"canonical_bits must contain exactly {width} binary digits")
    return tuple(int(b) for b in canonical_bits)


@dataclass(frozen=True)
class Qubo:
    """Q(x) = constant + sum(linear[i] x_i) + sum(quadratic[i,j] x_i x_j).

    Each unordered pair occurs once, with i < j; coefficients are not a symmetric
    matrix and must not be doubled when evaluating or converting them.
    """

    action_order: tuple[str, ...]
    constant: float
    linear: tuple[float, ...]
    quadratic: dict[tuple[int, int], float]

    def evaluate(self, canonical_bits: str) -> float:
        bits = _bits(canonical_bits, len(self.action_order))
        return float(
            self.constant
            + sum(a * b for a, b in zip(self.linear, bits))
            + sum(a * bits[i] * bits[j] for (i, j), a in self.quadratic.items())
        )


@dataclass(frozen=True)
class IsingCost:
    operator: SparsePauliOp
    offset: float
    action_order: tuple[str, ...]


def build_qubo(scenario: dict, alpha: float | None = None) -> Qubo:
    """Encode the shared core model, retaining penalties on every invalid plan.

    This validates the assumptions needed by this encoding, not the complete
    shared JSON schema. Use scoring.load_scenario for authoritative input loading.
    In particular a three-candidate encounter is higher-order and is rejected.
    """
    objective = scenario["objective"]
    alpha = _finite_number(
        objective["default_alpha"] if alpha is None else alpha, "alpha"
    )
    if not 0 <= alpha <= 1:
        raise ValueError("alpha must be in [0, 1]")
    fuel_norm, reserve_norm, penalty = (
        _finite_number(objective[key], key)
        for key in ("fuel_normalization", "reserve_normalization", "violation_penalty")
    )
    if min(fuel_norm, reserve_norm, penalty) <= 0:
        raise ValueError("normalizations and violation_penalty must be positive")

    order = tuple(scenario["action_order"])
    records = scenario["actions"]
    by_id = {a["id"]: a for a in records}
    if (not order or len(set(order)) != len(order) or len(by_id) != len(records)
            or set(order) != set(by_id)):
        raise ValueError("action_order must contain each unique action exactly once")
    actions = [by_id[action_id] for action_id in order]
    companies, encounters = scenario["companies"], scenario["encounters"]
    if len(set(companies)) != len(companies) or len(set(encounters)) != len(encounters):
        raise ValueError("companies and encounters must be unique")
    fuel, ratios = [], []
    for a in actions:
        f = _finite_number(a["fuel"], "fuel")
        reserve = _finite_number(a["remaining_reserve"], "remaining_reserve")
        if not 0 < f <= reserve:
            raise ValueError("actions require 0 < fuel <= remaining_reserve")
        if type(a["available"]) is not bool:
            raise TypeError("action availability must be boolean")
        if a["company"] not in companies:
            raise ValueError("action refers to an unknown company")
        if len(set(a["covers"])) != len(a["covers"]) or not set(a["covers"]) <= set(encounters):
            raise ValueError("action coverage must contain unique declared encounters")
        fuel.append(f)
        ratios.append(f / reserve)
    bound = sum(
        sum(r for a, r in zip(actions, ratios) if a["company"] == company) ** 2
        for company in companies
    )
    if sum(fuel) > fuel_norm or bound > reserve_norm:
        raise ValueError("declared normalization is below the computed all-action bound")

    linear = [(1 - alpha) * f / fuel_norm + alpha * r * r / reserve_norm
              + (0 if a["available"] else penalty)
              for a, f, r in zip(actions, fuel, ratios)]
    quadratic = {}
    for i, a in enumerate(actions):
        for j in range(i + 1, len(actions)):
            if a["company"] == actions[j]["company"]:
                quadratic[i, j] = 2 * alpha * ratios[i] * ratios[j] / reserve_norm
    # An uncovered encounter is (1-x_i)(1-x_j), even if i or j is unavailable.
    for encounter in encounters:
        candidates = [i for i, a in enumerate(actions) if encounter in a["covers"]]
        if len(candidates) != 2:
            raise ValueError("each core encounter must have exactly two candidate actions")
        i, j = candidates
        linear[i] -= penalty
        linear[j] -= penalty
        quadratic[i, j] = quadratic.get((i, j), 0.0) + penalty
    return Qubo(order, penalty * len(encounters), tuple(linear), quadratic)


def qubo_to_ising(qubo: Qubo) -> IsingCost:
    """Substitute x_i=(1-Z_i)/2; Pauli label's rightmost character is qubit 0."""
    width = len(qubo.action_order)
    z = [-a / 2 for a in qubo.linear]
    offset = qubo.constant + sum(qubo.linear) / 2
    terms = []
    for (i, j), coefficient in qubo.quadratic.items():
        weight = coefficient / 4
        offset += weight
        z[i] -= weight
        z[j] -= weight
        label = ["I"] * width
        label[width - 1 - i] = label[width - 1 - j] = "Z"
        terms.append(("".join(label), weight))
    for i, coefficient in enumerate(z):
        label = ["I"] * width
        label[width - 1 - i] = "Z"
        terms.append(("".join(label), coefficient))
    # Do not simplify with an absolute tolerance: retain small real coefficients.
    return IsingCost(SparsePauliOp.from_list(terms), float(offset), qubo.action_order)


def build_qaoa_circuit(cost: IsingCost, gamma: float, beta: float,
                       measure: bool = False) -> QuantumCircuit:
    """One layer: exp(-i beta sum X) exp(-i gamma H_C) |+>^n.

    The tracked offset is a global phase and need not be applied as a gate.
    """
    gamma, beta = _finite_number(gamma, "gamma"), _finite_number(beta, "beta")
    width = len(cost.action_order)
    circuit = QuantumCircuit(width, width if measure else 0)
    circuit.h(range(width))
    for label, coefficient in cost.operator.to_list():
        if complex(coefficient).imag != 0 or not isfinite(complex(coefficient).real):
            raise ValueError("cost coefficients must be finite and real")
        qubits = [i for i, pauli in enumerate(reversed(label)) if pauli != "I"]
        if any(pauli not in "IZ" for pauli in label) or len(qubits) not in (1, 2):
            raise ValueError("the core cost operator must contain only Z and ZZ terms")
        angle = 2 * gamma * float(complex(coefficient).real)
        if len(qubits) == 1:
            circuit.rz(angle, qubits[0])
        else:
            circuit.rzz(angle, *qubits)
    circuit.rx(2 * beta, range(width))
    if measure:
        circuit.measure(range(width), range(width))
    return circuit


def verify_measurement_mapping(circuit: QuantumCircuit, num_actions: int) -> None:
    """Require one full-width register, final q_i->c_i measurements, no routing.

    Arbitrary layouts need an explicit logical mapping; refusing them avoids a
    plausible but incorrect reversal. Call this again after transpilation.
    """
    width = _positive_integer(num_actions, "num_actions")
    if (circuit.num_qubits != width or circuit.num_clbits != width
            or len(circuit.cregs) != 1 or len(circuit.cregs[0]) != width):
        raise ValueError("expected one classical register matching the action width")
    if circuit.layout is not None and circuit.layout.final_index_layout() != list(range(width)):
        raise ValueError("nonidentity transpilation layout needs explicit decoding")
    mapping = {}
    measurement_started = False
    for instruction in circuit.data:
        name = instruction.operation.name
        if name == "measure":
            measurement_started = True
            q = circuit.find_bit(instruction.qubits[0]).index
            c = circuit.find_bit(instruction.clbits[0]).index
            if q in mapping:
                raise ValueError("each qubit must be measured exactly once")
            mapping[q] = c
        elif measurement_started and name != "barrier":
            raise ValueError("measurements must be final")
    if mapping != dict(enumerate(range(width))):
        raise ValueError("expected qubit i measured into classical bit i")


def decode_counts(raw_counts: Mapping[str, int], circuit: QuantumCircuit) -> dict[str, int]:
    """Decode standard displayed Qiskit counts ONCE; never pass canonical counts."""
    verify_measurement_mapping(circuit, circuit.num_qubits)
    width = circuit.num_qubits
    canonical = {}
    for raw, count in raw_counts.items():
        _bits(raw, width)  # Reject integers, hex, spaces, and multiple registers.
        if isinstance(count, bool) or not isinstance(count, Integral) or count < 0:
            raise ValueError("counts must be nonnegative integers")
        canonical[raw[::-1]] = int(count)
    return canonical


def decode_state_index(index: int, num_actions: int) -> str:
    """Read action i from bit i of a statevector index, without string reversal."""
    width = _positive_integer(num_actions, "num_actions")
    if isinstance(index, bool) or not isinstance(index, Integral) or not 0 <= index < 2**width:
        raise ValueError("state index is outside the action register")
    return "".join(str((index >> i) & 1) for i in range(width))


def optimize_qaoa(cost: IsingCost, *, seed: int = 7, shots: int = 4096,
                  maxiter: int = 200, starts: int = 4) -> dict:
    """Optimize the exact, unconditioned ideal expectation, then measure once.

    No validity filtering is done during optimization. Starts are drawn from a
    seeded generator. Failed optimizations remain in the report; only successful
    starts can supply final angles. No classical plan is substituted on failure.
    """
    shots = _positive_integer(shots, "shots")
    maxiter = _positive_integer(maxiter, "maxiter")
    starts = _positive_integer(starts, "starts")
    if isinstance(seed, bool) or not isinstance(seed, Integral) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    rng = np.random.default_rng(seed)

    def expectation(angles):
        state = Statevector.from_instruction(build_qaoa_circuit(cost, *angles))
        return float(state.expectation_value(cost.operator).real + cost.offset)

    attempts = []
    for _ in range(starts):
        initial = rng.uniform([0, 0], [2 * np.pi, np.pi]).tolist()
        result = minimize(expectation, initial, method="COBYLA", options={
            "maxiter": maxiter, "tol": 1e-8, "rhobeg": 0.5,
        })
        attempts.append({
            "initial_angles": initial, "initial_expectation": expectation(initial),
            "angles": result.x.tolist(), "expectation": float(result.fun),
            "success": bool(result.success), "message": str(result.message),
            "evaluations": int(result.nfev),
        })
    converged = [attempt for attempt in attempts if attempt["success"]
                 and isfinite(attempt["expectation"])]
    if not converged:
        raise RuntimeError(f"No QAOA start converged; no sample substituted: {attempts}")
    best = min(converged, key=lambda attempt: attempt["expectation"])
    gamma, beta = best["angles"]
    simulator = BasicSimulator()
    measured = build_qaoa_circuit(cost, gamma, beta, measure=True)
    verify_measurement_mapping(measured, len(cost.action_order))
    compiled = transpile(measured, simulator, seed_transpiler=seed, optimization_level=1)
    verify_measurement_mapping(compiled, len(cost.action_order))
    raw = dict(simulator.run(compiled, shots=shots, seed_simulator=seed).result().get_counts())
    canonical = decode_counts(raw, compiled)
    return {
        "algorithm": "QAOA", "layers": 1, "simulator": "BasicSimulator (ideal)",
        "action_order": list(cost.action_order), "shots": shots,
        "seed": int(seed), "seed_simulator": int(seed), "seed_transpiler": int(seed),
        "optimizer": {"method": "COBYLA", "maxiter": maxiter, "starts": starts,
                      "tol": 1e-8, "rhobeg": 0.5,
                      "objective": "exact expectation including all violation penalties"},
        "angles": {"gamma": gamma, "beta": beta},
        "expectation": best["expectation"], "constant_offset": cost.offset,
        "attempts": attempts, "raw_counts": raw, "canonical_counts": canonical,
        "bit_mapping": "action i -> qubit i -> classical bit i; raw strings c[n-1]...c[0]",
        "measurement_mapping_verified_before_and_after_transpilation": True,
        "transpile_optimization_level": 1,
        "versions": {name: version(name) for name in ("qiskit", "numpy", "scipy")},
    }


def summarize_samples(scenario: dict, canonical_counts: Mapping[str, int], alpha: float,
                      *, optimal_bits: Collection[str]) -> dict:
    """Use the real scorer and an externally established COMPLETE optimal set.

    The caller supplies authoritative classical reference optima; this module does
    not enumerate them. Both rates use all raw shots, including invalid samples.
    """
    from scoring import evaluate_plan

    reference = set(optimal_bits)
    scores = [evaluate_plan(scenario, bits, alpha) for bits in reference]
    if any(not plan["valid"] for plan in scores):
        raise ValueError("reference optimal plans must be valid under modeled rules")
    if scores and not np.allclose([p["objective_score"] for p in scores],
                                  scores[0]["objective_score"], rtol=0, atol=1e-10):
        raise ValueError("reference optimal plans must have equal objective scores")
    total = valid = optimal = 0
    objective_sum = 0.0
    for bits, count in canonical_counts.items():
        if isinstance(count, bool) or not isinstance(count, Integral) or count < 0:
            raise ValueError("counts must be nonnegative integers")
        plan = evaluate_plan(scenario, bits, alpha)
        total += int(count)
        valid += int(count) if plan["valid"] else 0
        optimal += int(count) if bits in reference else 0
        objective_sum += count * plan["objective_score"]
    if total == 0:
        raise ValueError("sample rates require at least one shot")
    return {"shots": total, "valid_samples": valid, "optimal_samples": optimal,
            "valid_sample_rate": valid / total, "optimal_sample_rate": optimal / total,
            "sampled_mean_objective": objective_sum / total,
            "reference_optimal_bits": sorted(reference),
            "reference_feasible": bool(reference)}
