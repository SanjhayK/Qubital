"""Separately recorded, local p=1 optimizer robustness follow-up to v2.

No IBM imports or submission path. The model, old runner and old results are
unchanged. Fast training evolves the same six-qubit state as the Qiskit circuit;
final measurements always use that Qiskit circuit on BasicSimulator.
"""

import argparse
import csv
from datetime import datetime, timezone
from importlib.metadata import version
import json
import math
from pathlib import Path
import platform
import subprocess
import time

import numpy as np
from qiskit import transpile
from qiskit.providers.basic_provider import BasicSimulator
from qiskit.quantum_info import Statevector
from scipy.optimize import minimize

from quantum import build_qaoa_circuit, decode_counts, verify_measurement_mapping
from research.experiments import sample_metrics, verify_encoding, write_json
from research.artifacts import digest, verify_preserved, verify_source
from research.socrates_gate import adapt_case
from research.verify_results import verify as verify_v2

ROOT = Path(__file__).resolve().parents[1]
CASES = ("unit-debris-off", "unit-debris-on", "priority-debris-off", "priority-debris-on")
SETTINGS = {
    "study_id": "qubital.p1.optimizer-robustness.v1",
    "model_id": "qubital.responsibility.v1", "layers": 1, "eta": .5,
    "cases": list(CASES), "training_seeds": [7, 19, 43], "starts_per_seed": 4,
    "optimizer": "COBYLA", "max_evaluations_per_start": 2000,
    "tolerance": 1e-6, "rhobeg": .5, "shots_per_run": 4096,
    "initialization": "default_rng(seed), four successive uniform draws from [0,2pi] x [0,pi]; first matches v2",
    "angle_bounds": None,
    "selection": "lowest best-visited expectation among formally converged starts; if none, lowest among all starts, flagged ineligible for hardware",
    "selection_ties": "start index; hardware candidate ties by seed",
    "sampling": "one 4096-shot Qiskit circuit for the selected start per case/seed, not per start",
    "training": "exact six-qubit statevector from Ising diagonal and RX mixers; no exact-optimum lookup",
    "qiskit_checks": "every start's initial, best-visited and returned angles; selected full probability distribution",
    "near_optimal_absolute_threshold": .02, "optimum_absolute_tolerance": 1e-12,
    "convergence_meaning": "COBYLA success at declared trust-region tolerance, not a global-optimality certificate",
    "baselines": "reuse verified immutable v2 exact/uniform/annealing records; same cases and 4096 returned samples, unequal computation",
    "study_scope": "v2-informed within-dataset optimizer robustness, not independent data validation or quantum advantage",
    "hardware_target": "priority-debris-on, fixed before training; lowest expectation among converged selected seeds only after all-case comparison",
    "hardware_recommendation_gate": "all 12 selected runs formally converged and every case's mean exact expectation no worse than v2 within 1e-10; target candidate no worse than best v2 target expectation within 1e-10",
    "execution_type": "ideal_simulator", "hardware_jobs_authorized": False,
    "hardware_jobs_submitted": 0,
}


def starts_for_seed(seed, count):
    rng = np.random.default_rng(seed)
    return [rng.uniform([0, 0], [2 * np.pi, np.pi]).tolist() for _ in range(count)]


class P1State:
    """Small ideal state simulator using little-endian Ising basis indices.

    This changes execution overhead, not the cost function or QAOA ansatz.
    Restrict dimensions to prevent accidental simulation of full-device circuits.
    """

    def __init__(self, cost):
        self.width = len(cost.action_order)
        if not 1 <= self.width <= 10:
            raise ValueError("small logical statevectors only")
        matrix = cost.operator.to_matrix()
        diagonal = np.diag(matrix)
        if not np.allclose(matrix, np.diag(diagonal), rtol=0, atol=1e-14):
            raise ValueError("diagonal Ising cost required")
        if not np.isfinite(diagonal).all() or np.any(diagonal.imag != 0):
            raise ValueError("finite real cost required")
        self.diagonal = diagonal.real
        self.offset = cost.offset

    def probabilities(self, angles):
        gamma, beta = np.asarray(angles, dtype=float)
        if not np.isfinite([gamma, beta]).all():
            raise ValueError("finite angles required")
        state = np.exp(-1j * gamma * self.diagonal) / math.sqrt(2 ** self.width)
        c, s = math.cos(beta), -1j * math.sin(beta)
        for qubit in range(self.width):
            pairs = state.reshape(-1, 2, 2 ** qubit)
            zero, one = pairs[:, 0, :].copy(), pairs[:, 1, :].copy()
            pairs[:, 0, :] = c * zero + s * one
            pairs[:, 1, :] = s * zero + c * one
        return np.abs(state) ** 2

    def expectation(self, angles):
        return float(self.probabilities(angles) @ self.diagonal + self.offset)


def qiskit_expectation(cost, angles):
    state = Statevector.from_instruction(build_qaoa_circuit(cost, *angles))
    return float(state.expectation_value(cost.operator).real + cost.offset)


def check_angles(cost, engine, angles):
    error = abs(engine.expectation(angles) - qiskit_expectation(cost, angles))
    if error > 1e-12:
        raise ValueError("training engine disagrees with Qiskit")
    return error


def train_start(cost, initial, settings):
    engine, history = P1State(cost), []
    started = time.perf_counter()

    def objective(angles):
        if len(history) >= settings["max_evaluations_per_start"]:
            raise RuntimeError("optimizer exceeded the declared evaluation budget")
        value = engine.expectation(angles)
        if not math.isfinite(value):
            raise ValueError("nonfinite expectation")
        history.append({"angles": np.asarray(angles).tolist(), "expectation": value})
        return value

    fitted = minimize(objective, initial, method="COBYLA", options={
        "maxiter": settings["max_evaluations_per_start"], "tol": settings["tolerance"],
        "rhobeg": settings["rhobeg"],
    })
    best = min(history, key=lambda row: row["expectation"])
    checked = (initial, best["angles"], fitted.x.tolist())
    error = max(check_angles(cost, engine, angles) for angles in checked)
    return {"initial_angles": initial, "history": history,
            "best_angles": best["angles"], "best_expectation": best["expectation"],
            "returned_angles": fitted.x.tolist(), "returned_expectation": float(fitted.fun),
            "optimizer_converged": bool(fitted.success), "optimizer_status": int(fitted.status),
            "optimizer_message": str(fitted.message), "evaluations": len(history),
            "reported_nfev": int(fitted.nfev), "seconds": time.perf_counter() - started,
            "qiskit_check_max_error": error}


def select_attempt(attempts):
    if not attempts:
        raise ValueError("no training attempts")
    converged = [a for a in attempts if a["optimizer_converged"]]
    return min(converged or attempts, key=lambda a: (a["best_expectation"], a["start_index"]))


def sample_selected(cost, selected, seed, shots):
    angles = selected["best_angles"]
    circuit = build_qaoa_circuit(cost, *angles, measure=True)
    verify_measurement_mapping(circuit, len(cost.action_order))
    compiled = transpile(circuit, BasicSimulator(), seed_transpiler=seed, optimization_level=1)
    verify_measurement_mapping(compiled, len(cost.action_order))
    raw = dict(BasicSimulator().run(compiled, shots=shots, seed_simulator=seed).result().get_counts())
    expected = Statevector.from_instruction(build_qaoa_circuit(cost, *angles)).probabilities()
    error = float(np.max(np.abs(P1State(cost).probabilities(angles) - expected)))
    if error > 1e-12:
        raise ValueError("selected probability distribution disagrees with Qiskit")
    return {"angles": dict(zip(("gamma", "beta"), angles)),
            "raw_counts": raw, "counts": decode_counts(raw, compiled),
            "shots": shots, "seed_simulator": seed, "seed_transpiler": seed,
            "measurement_mapping_verified": True, "probability_check_max_error": error,
            "logical_depth": circuit.depth(),
            "logical_two_qubit_gates": sum(len(i.qubits) == 2 for i in circuit.data)}


def check_preservation(output):
    manifest = json.loads((Path(output) / "preserved-files.json").read_text())
    return verify_preserved(ROOT, manifest, completed=(Path(output) / "completed.json").is_file())


def plan(snapshot_root, baseline, output):
    output, baseline = Path(output), Path(baseline).resolve()
    verified = verify_v2(snapshot_root, baseline)
    output.mkdir(parents=True, exist_ok=False)
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    preserved = {name: digest(ROOT / name) for name in tracked if name}
    write_json(output / "preserved-files.json", preserved)
    sources = ("research/robustness.py", "research/verify_robustness.py", "research/artifacts.py")
    protocol = dict(SETTINGS, frozen_at_utc=datetime.now(timezone.utc).isoformat(),
                    baseline_directory=baseline.relative_to(ROOT).as_posix(),
                    baseline_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
                    baseline_verification=verified, preserved_files_sha256=digest(output / "preserved-files.json"),
                    python=platform.python_version(),
                    versions={name: version(name) for name in ("qiskit", "numpy", "scipy")},
                    source_sha256={name: digest(ROOT / name) for name in sources},
                    initial_starts={str(seed): starts_for_seed(seed, SETTINGS["starts_per_seed"])
                                    for seed in SETTINGS["training_seeds"]})
    for name in sources:
        (output / (Path(name).name + ".txt")).write_bytes((ROOT / name).read_bytes())
    write_json(output / "protocol.json", protocol)
    return {"protocol_sha256": digest(output / "protocol.json"), "preserved_files": len(preserved),
            "planned_starts": 48, "maximum_optimizer_evaluations": 96000,
            "planned_final_shots": 49152, "training_started": False}


def read_protocol(output):
    output = Path(output)
    protocol = json.loads((output / "protocol.json").read_text())
    if any(protocol[key] != value for key, value in SETTINGS.items()):
        raise ValueError("settings differ from the frozen protocol")
    if digest(output / "preserved-files.json") != protocol["preserved_files_sha256"]:
        raise ValueError("preservation manifest changed")
    for name, expected in protocol["source_sha256"].items():
        verify_source(ROOT, name, expected, output / (Path(name).name + ".txt"),
                      completed=(output / "completed.json").is_file())
    check_preservation(output)
    return protocol


def run(snapshot_root, output):
    output = Path(output)
    protocol = read_protocol(output)
    if list(output.glob("*-qaoa_p1.json")) or (output / "started.json").exists():
        raise ValueError("choose a new study directory; partial/completed runs are not overwritten")
    write_json(output / "started.json", {"at_utc": datetime.now(timezone.utc).isoformat(),
                                        "protocol_sha256": digest(output / "protocol.json")})
    baseline = ROOT / protocol["baseline_directory"]
    records = []
    for case_name in protocol["cases"]:
        variant = case_name.split("-")[0]
        background = case_name.endswith("-on")
        case = adapt_case(snapshot_root, variant)
        _, cost, scores, error = verify_encoding(case, protocol["eta"], background)
        minimum = min(scores.values())
        optimum = sorted(b for b, score in scores.items() if abs(score - minimum) <= 1e-12)
        for seed in protocol["training_seeds"]:
            started = time.perf_counter()
            attempts = []
            for index, initial in enumerate(protocol["initial_starts"][str(seed)]):
                attempt = dict(train_start(cost, initial, protocol), start_index=index,
                               case=case_name, seed=seed)
                write_json(output / f"{case_name}-{seed}-start-{index}.json", attempt)
                attempts.append(attempt)
            selected = select_attempt(attempts)
            sampled = sample_selected(cost, selected, seed, protocol["shots_per_run"])
            record = {"study_id": protocol["study_id"], "model_id": case["model_id"],
                      "case": case_name, "seed": seed, "eta": protocol["eta"],
                      "W_ref": case["W_ref"], "data_sha256": case["source_sha256"],
                      "execution_type": "ideal_simulator", "selected_start": selected["start_index"],
                      "selected_optimizer_converged": selected["optimizer_converged"],
                      "converged_starts": sum(a["optimizer_converged"] for a in attempts),
                      "total_starts": len(attempts), "expectation": selected["best_expectation"],
                      "best_expectation_all_starts": min(a["best_expectation"] for a in attempts),
                      "expectation_regret": selected["best_expectation"] - minimum,
                      "optimizer_evaluations": sum(a["evaluations"] for a in attempts),
                      "encoding_max_error": error, "exact_minimum": minimum,
                      "complete_optimal_bits": optimum, "classical_substitution": False,
                      "seconds": time.perf_counter() - started, **sampled,
                      "metrics": sample_metrics(sampled["counts"], scores, minimum, optimum)}
            write_json(output / f"{case_name}-{seed}-qaoa_p1.json", record)
            records.append(record)
            print(f"{case_name} seed {seed}: {record['converged_starts']}/4 converged; "
                  f"E={record['expectation']:.9f}, hit={record['metrics']['complete_optimum_hit_probability']:.4f}", flush=True)
    write_comparison(output, baseline, records)
    check_preservation(output)
    write_json(output / "completed.json", {"at_utc": datetime.now(timezone.utc).isoformat(),
                                          "hardware_jobs_submitted": 0})


def write_comparison(output, baseline, records):
    rows = []
    for record in records:
        common = {"case": record["case"], "seed": record["seed"]}
        rows.append(common | {"method": "qaoa_p1_robustness", **record["metrics"],
            "expectation": record["expectation"], "expectation_regret": record["expectation_regret"],
            "optimizer_converged": record["selected_optimizer_converged"],
            "converged_starts": record["converged_starts"], "total_starts": record["total_starts"],
            "optimizer_evaluations": record["optimizer_evaluations"], "seconds": record["seconds"]})
        for method in ("qaoa_p1", "uniform", "annealing_best_of_independent_chains"):
            previous = json.loads((baseline / f"{record['case']}-{record['seed']}-{method}.json").read_text())
            trained = previous.get("training_and_sampling", {})
            rows.append(common | {"method": method + "_v2", **previous["metrics"],
                "expectation": trained.get("expectation"),
                "expectation_regret": previous.get("exact_expectation_regret"),
                "optimizer_converged": previous.get("optimizer_converged"),
                "converged_starts": int(previous["optimizer_converged"]) if method == "qaoa_p1" else None,
                "total_starts": 1 if method == "qaoa_p1" else None,
                "optimizer_evaluations": previous.get("optimizer_evaluations"),
                "seconds": previous["seconds"]})
    write_json(output / "comparison.json", rows)
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with (output / "comparison.csv").open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys, lineterminator="\n")
        writer.writeheader()
        writer.writerows({k: json.dumps(v) if isinstance(v, list) else v for k, v in row.items()} for row in rows)
    aggregate = []
    for case_name in CASES:
        for method in dict.fromkeys(row["method"] for row in rows):
            selected = [row for row in rows if row["case"] == case_name and row["method"] == method]
            item = {"case": case_name, "method": method, "seeds": len(selected)}
            for key in ("complete_optimum_hit_probability", "absolute_regret", "expectation", "expectation_regret"):
                values = [row[key] for row in selected if row.get(key) is not None]
                item[key] = {"mean": math.fsum(values) / len(values), "min": min(values), "max": max(values)} if values else None
            item["selected_converged_runs"] = sum(row["optimizer_converged"] is True for row in selected)
            item["converged_starts"] = sum(row["converged_starts"] or 0 for row in selected)
            item["total_starts"] = sum(row["total_starts"] or 0 for row in selected)
            aggregate.append(item)
    write_json(output / "aggregate.json", aggregate)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("plan", "run"))
    parser.add_argument("--snapshot-root", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, default=ROOT / "results/responsibility-p1-20261114-v2")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.phase == "plan":
        print(json.dumps(plan(args.snapshot_root, args.baseline, args.output), indent=2))
    else:
        run(args.snapshot_root, args.output)
