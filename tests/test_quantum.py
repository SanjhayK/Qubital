"""Quantum encoding checks, with explicit integration skips until scoring merges."""

import copy
import importlib
import itertools
import json
from pathlib import Path

import numpy as np
import pytest
from qiskit import ClassicalRegister, QuantumCircuit, transpile
from qiskit.providers.basic_provider import BasicSimulator
from qiskit.quantum_info import SparsePauliOp, Statevector

from quantum import (
    IsingCost,
    build_qaoa_circuit,
    build_qubo,
    decode_counts,
    decode_state_index,
    optimize_qaoa,
    qubo_to_ising,
    summarize_samples,
    verify_measurement_mapping,
)


SCENARIO_PATH = Path(__file__).resolve().parents[1] / "data" / "original.json"
ALPHAS = (0.0, 0.25, 0.5, 1.0)


@pytest.fixture
def scenario():
    # This fixture reads input bytes; it does not provide a substitute scorer.
    return json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def scorer():
    try:
        return importlib.import_module("scoring")
    except ModuleNotFoundError as exc:
        if exc.name != "scoring":
            raise
        pytest.skip("Authoritative scoring.py is not on this branch; integration pending")


def bit_patterns(width):
    return ("".join(bits) for bits in itertools.product("01", repeat=width))


def basis_energy(cost, canonical_bits):
    # Qiskit basis indices assign the least significant bit to qubit zero.
    index = int(canonical_bits[::-1], 2)
    state = Statevector.from_int(index, 2 ** len(canonical_bits))
    return float(state.expectation_value(cost.operator).real) + cost.offset


@pytest.mark.parametrize("alpha", ALPHAS)
def test_all_basis_energies_equal_qubo_including_offset(scenario, alpha):
    qubo = build_qubo(scenario, alpha)
    cost = qubo_to_ising(qubo)

    assert cost.action_order == tuple(scenario["action_order"])
    assert cost.operator.num_qubits == 6
    assert all(set(label) <= {"I", "Z"} for label in cost.operator.paulis.to_labels())
    assert "IIIIII" not in cost.operator.paulis.to_labels()
    for bits in bit_patterns(6):
        assert basis_energy(cost, bits) == pytest.approx(
            qubo.evaluate(bits), abs=1e-12
        ), bits


def test_known_coefficients_and_offset(scenario):
    qubo = build_qubo(scenario, 0.25)
    cost = qubo_to_ising(qubo)

    assert qubo.constant == 8.0
    assert qubo.linear == pytest.approx(
        (
            -3.8303048034133225,
            -1.828601255333316,
            -1.821219213653289,
            -1.8977383546665976,
            -3.8888564745637186,
            -1.8977383546665976,
        ),
        abs=1e-13,
    )
    assert qubo.quadratic[(0, 3)] == 2.0
    assert qubo.quadratic[(0, 4)] == 2.0
    assert qubo.quadratic[(1, 4)] == 2.0
    assert qubo.quadratic[(2, 5)] == 2.0
    assert qubo.quadratic[(0, 1)] == pytest.approx(
        2 * 0.25 * 0.1 * 0.125 / 0.8254830119
    )
    assert cost.offset == pytest.approx(2.458885359856578, abs=1e-13)
    assert qubo.evaluate("000000") == 8.0
    assert qubo.evaluate("100011") == pytest.approx(
        0.42898718432622596, abs=1e-13
    )
    assert qubo.evaluate("111111") == pytest.approx(
        0.75 + 0.25 * 0.8254826675849403 / 0.8254830119,
        abs=1e-12,
    )


def test_normalizations_and_penalty_come_from_scenario(scenario):
    changed = copy.deepcopy(scenario)
    changed["objective"].update(
        fuel_normalization=18.0,
        reserve_normalization=1.6509660238,
        violation_penalty=3.0,
    )
    original = build_qubo(scenario, 0.25)
    qubo = build_qubo(changed, 0.25)

    assert qubo.constant == 12.0
    assert qubo.evaluate("000000") == 12.0
    assert qubo.evaluate("100011") == pytest.approx(
        original.evaluate("100011") / 2, abs=1e-12
    )
    assert qubo.quadratic[(0, 3)] == 3.0


def test_availability_adds_penalty_without_removing_coverage(scenario):
    changed = copy.deepcopy(scenario)
    next(a for a in changed["actions"] if a["id"] == "B2")["available"] = False
    original = build_qubo(scenario, 0.25)
    qubo = build_qubo(changed, 0.25)

    assert qubo.quadratic == original.quadratic
    assert qubo.constant == original.constant
    for bits in bit_patterns(6):
        assert qubo.evaluate(bits) - original.evaluate(bits) == pytest.approx(
            2.0 if bits[4] == "1" else 0.0, abs=1e-12
        )


def test_action_order_controls_qubit_assignment_and_input_is_unchanged(scenario):
    before = copy.deepcopy(scenario)
    original = build_qubo(scenario)
    assert scenario == before
    assert original.evaluate("100011") == pytest.approx(
        build_qubo(scenario, 0.25).evaluate("100011")
    )

    reordered = copy.deepcopy(scenario)
    reordered["action_order"] = list(reversed(scenario["action_order"]))
    # The records stay in their original order; the canonical order is authoritative.
    qubo = build_qubo(reordered, 0.25)
    assert qubo.action_order == tuple(reordered["action_order"])
    for bits in bit_patterns(6):
        assert qubo.evaluate(bits[::-1]) == pytest.approx(
            original.evaluate(bits), abs=1e-12
        )


@pytest.mark.parametrize("alpha", [-0.01, 1.01, np.nan, np.inf, -np.inf, True, "0.25"])
def test_invalid_alpha_is_rejected(scenario, alpha):
    with pytest.raises((TypeError, ValueError)):
        build_qubo(scenario, alpha)


@pytest.mark.parametrize("field", ["fuel_normalization", "reserve_normalization"])
def test_understated_normalization_is_rejected(scenario, field):
    scenario["objective"][field] /= 2
    with pytest.raises(ValueError):
        build_qubo(scenario, 0.25)


def test_conservatively_rounded_reserve_bound_is_accepted(scenario):
    # In particular, no exact-equality check against the computed bound is valid.
    assert scenario["objective"]["reserve_normalization"] > 0.8254826675849403
    build_qubo(scenario, 0.25)


def test_more_than_two_coverage_candidates_is_rejected(scenario):
    scenario["actions"][1]["covers"].append("E1")
    with pytest.raises(ValueError):
        build_qubo(scenario, 0.25)


@pytest.mark.parametrize("bits", ["", "10001", "1000111", "10001x", 35])
def test_qubo_requires_canonical_binary_string(scenario, bits):
    with pytest.raises((TypeError, ValueError)):
        build_qubo(scenario, 0.25).evaluate(bits)


def test_one_layer_matches_direct_phase_and_tensor_product_mixer(scenario):
    gamma, beta = 0.731, -0.217
    qubo = build_qubo(scenario, 0.25)
    cost = qubo_to_ising(qubo)
    circuit = build_qaoa_circuit(cost, gamma, beta)
    actual = Statevector.from_instruction(circuit).data

    # This reference uses the full QUBO, including its constant, to verify the
    # circuit's phase sign and factor of two independently of its Pauli gates.
    energies = np.array(
        [qubo.evaluate(format(i, "06b")[::-1]) for i in range(64)]
    )
    phased = np.exp(-1j * gamma * energies) / 8
    mixer_one = np.array(
        [[np.cos(beta), -1j * np.sin(beta)],
         [-1j * np.sin(beta), np.cos(beta)]]
    )
    mixer = np.array([[1.0]])
    for _ in range(6):
        mixer = np.kron(mixer, mixer_one)
    reference = mixer @ phased

    # The tracked offset is omitted from gates, so global phase may differ.
    assert abs(np.vdot(reference, actual)) == pytest.approx(1.0, abs=1e-12)
    assert np.vdot(actual, energies * actual).real == pytest.approx(
        np.vdot(reference, energies * reference).real, abs=1e-12
    )


def test_penalties_remain_in_full_distribution_expectation(scenario):
    qubo = build_qubo(scenario, 0.25)
    cost = qubo_to_ising(qubo)
    state = Statevector.from_instruction(build_qaoa_circuit(cost, 0.0, 0.0))
    expected = sum(qubo.evaluate(bits) for bits in bit_patterns(6)) / 64
    assert state.expectation_value(cost.operator).real + cost.offset == pytest.approx(
        expected, abs=1e-12
    )
    # The uniform superposition includes the completely uncovered plan.
    assert abs(state.data[0]) ** 2 == pytest.approx(1 / 64)
    assert qubo.evaluate("000000") == 8.0


def test_nonhermitian_cost_is_rejected_instead_of_discarding_imaginary_part():
    cost = IsingCost(SparsePauliOp.from_list([("Z", 1 + 2j)]), 0.0, ("A1",))
    with pytest.raises(ValueError):
        build_qaoa_circuit(cost, 0.3, 0.2)


def test_seeded_optimizer_reports_unconditioned_expectation_and_real_counts(scenario):
    qubo = build_qubo(scenario, 0.25)
    cost = qubo_to_ising(qubo)
    result = optimize_qaoa(cost, seed=7, shots=32, maxiter=200, starts=1)
    repeat = optimize_qaoa(cost, seed=7, shots=32, maxiter=200, starts=1)
    angles = result["angles"]
    state = Statevector.from_instruction(
        build_qaoa_circuit(cost, angles["gamma"], angles["beta"])
    )
    energies = np.array(
        [qubo.evaluate(format(i, "06b")[::-1]) for i in range(64)]
    )

    assert result["expectation"] == pytest.approx(
        np.dot(state.probabilities(), energies), abs=1e-12
    )
    assert result["attempts"][0]["success"] is True
    assert result["expectation"] <= result["attempts"][0]["initial_expectation"]
    assert sum(result["raw_counts"].values()) == 32
    assert result["canonical_counts"] == {
        raw[::-1]: count for raw, count in result["raw_counts"].items()
    }
    assert repeat["angles"] == result["angles"]
    assert repeat["raw_counts"] == result["raw_counts"]


@pytest.mark.parametrize(
    "bits",
    ["100000", "010000", "001000", "000100", "000010", "000001",
     "100011", "000111", "110001", "111111"],
)
def test_measured_basis_patterns_decode_after_transpilation(bits):
    circuit = QuantumCircuit(6, 6)
    for i, bit in enumerate(bits):
        if bit == "1":
            circuit.x(i)
    circuit.measure(range(6), range(6))
    backend = BasicSimulator()
    compiled = transpile(circuit, backend, seed_transpiler=11)
    verify_measurement_mapping(compiled, 6)
    raw = backend.run(compiled, shots=8, seed_simulator=11).result().get_counts()

    assert raw == {bits[::-1]: 8}
    assert decode_counts(raw, compiled) == {bits: 8}
    index = sum((bit == "1") << i for i, bit in enumerate(bits))
    assert decode_state_index(index, 6) == bits


def test_qaoa_measurements_use_one_identity_mapped_classical_register(scenario):
    cost = qubo_to_ising(build_qubo(scenario, 0.25))
    circuit = build_qaoa_circuit(cost, 0.3, 0.2, measure=True)
    assert len(circuit.cregs) == 1
    assert circuit.num_clbits == 6
    verify_measurement_mapping(circuit, 6)
    assert decode_counts({"110001": 5}, circuit) == {"100011": 5}


def test_nonidentity_measurement_wiring_is_rejected():
    circuit = QuantumCircuit(6, 6)
    circuit.measure(range(6), reversed(range(6)))
    with pytest.raises(ValueError):
        verify_measurement_mapping(circuit, 6)
    with pytest.raises(ValueError):
        decode_counts({"110001": 1}, circuit)


def test_transpiler_permutation_is_not_silently_decoded_as_identity():
    circuit = QuantumCircuit(6, 6)
    circuit.x(0)
    circuit.measure(range(6), range(6))
    compiled = transpile(
        circuit, BasicSimulator(), initial_layout=[5, 4, 3, 2, 1, 0]
    )
    with pytest.raises(ValueError):
        decode_counts({"000001": 1}, compiled)


def test_multiple_classical_registers_are_rejected():
    circuit = QuantumCircuit(6)
    circuit.add_register(ClassicalRegister(3, "first"))
    circuit.add_register(ClassicalRegister(3, "second"))
    circuit.measure(range(6), range(6))
    with pytest.raises(ValueError):
        verify_measurement_mapping(circuit, 6)


@pytest.mark.parametrize("key", ["110 001", "0x31", "11001", "1100010", "11000x", 49])
def test_decoder_rejects_other_representations(key):
    circuit = QuantumCircuit(6, 6)
    circuit.measure(range(6), range(6))
    with pytest.raises((TypeError, ValueError)):
        decode_counts({key: 1}, circuit)


@pytest.mark.parametrize("count", [-1, 1.5, True])
def test_decoder_rejects_invalid_counts(count):
    circuit = QuantumCircuit(6, 6)
    circuit.measure(range(6), range(6))
    with pytest.raises((TypeError, ValueError)):
        decode_counts({"110001": count}, circuit)


@pytest.mark.parametrize("index", [-1, 64, 0.5, True])
def test_statevector_decoder_rejects_invalid_indices(index):
    with pytest.raises((TypeError, ValueError)):
        decode_state_index(index, 6)


@pytest.mark.parametrize("alpha", ALPHAS)
@pytest.mark.parametrize("unavailable", [(), ("B2",), ("A1", "B1")])
def test_authoritative_scorer_qubo_and_basis_energies(scorer, alpha, unavailable):
    scenario = scorer.load_scenario(SCENARIO_PATH)
    for action in scenario["actions"]:
        if action["id"] in unavailable:
            action["available"] = False
    qubo = build_qubo(scenario, alpha)
    cost = qubo_to_ising(qubo)
    plans = []

    for bits in bit_patterns(6):
        direct = scorer.evaluate_plan(scenario, bits, alpha)
        plans.append(direct)
        assert qubo.evaluate(bits) == pytest.approx(
            direct["objective_score"], abs=1e-12
        ), bits
        assert basis_energy(cost, bits) == pytest.approx(
            direct["objective_score"], abs=1e-12
        ), bits

    assert len(plans) == 64
    valid = [plan for plan in plans if plan["valid"]]
    if unavailable == ("A1", "B1"):
        assert valid == []
    else:
        if not unavailable:
            assert len(valid) == 24
        best_score = min(plan["objective_score"] for plan in valid)
        optimal_bits = {
            plan["canonical_bits"] for plan in valid
            if np.isclose(plan["objective_score"], best_score, rtol=0, atol=1e-12)
        }
        expected = (
            "110001" if unavailable == ("B2",)
            else {0.0: "000111", 0.25: "100011", 1.0: "110001"}.get(alpha)
        )
        if expected is not None:
            assert optimal_bits == {expected}


def test_sample_metrics_use_all_raw_samples_as_denominator(scorer):
    scenario = scorer.load_scenario(SCENARIO_PATH)
    counts = {"100011": 2, "111000": 3, "000000": 5}
    metrics = summarize_samples(
        scenario, counts, 0.25, optimal_bits={"100011"}
    )
    assert metrics["valid_sample_rate"] == 0.5
    assert metrics["optimal_sample_rate"] == 0.2
