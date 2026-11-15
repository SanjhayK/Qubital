"""Predeclared all-case BFGS cross-check after COBYLA budget exhaustion.

Additive follow-up only: no modification of v2 or the larger-budget COBYLA run.
Exact analytic p=1 state derivatives avoid finite-difference noise. All final
shots are still Qiskit BasicSimulator measurements, never classical substitutes.
"""

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import time

import numpy as np
from qiskit import qpy
from qiskit.quantum_info import Statevector
from scipy.optimize import minimize

from quantum import build_qaoa_circuit, decode_counts
from research.experiments import sample_metrics, verify_encoding, write_json
from research.artifacts import read_json, trace_paths, verify_preserved, verify_source
from research.robustness import (CASES, ROOT, SETTINGS as COBYLA_SETTINGS, P1State,
                                 check_angles, digest, sample_selected, select_attempt,
                                 starts_for_seed, write_comparison)
from research.socrates_gate import adapt_case
from research.verify_robustness import require, close, verify as verify_cobyla

SETTINGS = dict(COBYLA_SETTINGS,
    study_id="qubital.p1.optimizer-robustness.bfgs.v1", optimizer="BFGS",
    tolerance=1e-6, gradient_tolerance=1e-6, gradient_norm="infinity",
    max_iterations_per_start=2000, gradient="analytic exact-state derivatives",
    rhobeg=None,
    rationale="separately declared after COBYLA had nonconverged starts; all four cases, no outcome-selected starting angles",
    convergence_meaning="BFGS success plus independently recomputed infinity-norm gradient <=1e-6; not global optimality",
    hardware_recommendation_gate="all 12 selected runs formally converged, each case mean expectation no worse than v2 within 1e-10, and target best-visited angles have infinity-norm gradient <=1e-6 and expectation no worse than best v2 target within 1e-10",
)


class DifferentiableP1(P1State):
    def value_gradient(self, angles):
        gamma, beta = np.asarray(angles, dtype=float)
        if not np.isfinite([gamma, beta]).all():
            raise ValueError("finite angles required")
        state = np.exp(-1j * gamma * self.diagonal) / math.sqrt(2 ** self.width)
        dgamma = -1j * self.diagonal * state
        c, s = math.cos(beta), -1j * math.sin(beta)
        for qubit in range(self.width):
            for vector in (state, dgamma):
                pairs = vector.reshape(-1, 2, 2 ** qubit)
                zero, one = pairs[:, 0, :].copy(), pairs[:, 1, :].copy()
                pairs[:, 0, :] = c * zero + s * one
                pairs[:, 1, :] = s * zero + c * one
        dbeta = np.zeros_like(state)
        for qubit in range(self.width):
            dbeta += -1j * state.reshape(-1, 2, 2 ** qubit)[:, ::-1, :].reshape(-1)
        weighted = self.diagonal * state
        gradient = np.array([2 * np.vdot(dgamma, weighted).real, 2 * np.vdot(dbeta, weighted).real])
        return float(np.vdot(state, weighted).real + self.offset), gradient


class EvaluationBudget(RuntimeError):
    pass


def train_start(cost, initial, settings):
    engine, history = DifferentiableP1(cost), []
    started = time.perf_counter()

    def objective(angles):
        if len(history) >= settings["max_evaluations_per_start"]:
            raise EvaluationBudget()
        value, gradient = engine.value_gradient(angles)
        if not math.isfinite(value) or not np.isfinite(gradient).all():
            raise ValueError("nonfinite expectation/gradient")
        history.append({"angles": np.asarray(angles).tolist(), "expectation": value,
                        "gradient": gradient.tolist()})
        return value, gradient

    try:
        fitted = minimize(objective, initial, method="BFGS", jac=True, options={
            "gtol": settings["gradient_tolerance"], "norm": np.inf,
            "maxiter": settings["max_iterations_per_start"],
        })
        returned, value = fitted.x.tolist(), float(fitted.fun)
        status, message, success, nfev = int(fitted.status), str(fitted.message), bool(fitted.success), int(fitted.nfev)
    except EvaluationBudget:
        best = min(history, key=lambda step: step["expectation"])
        returned, value = best["angles"], best["expectation"]
        status, message, success, nfev = 10, "Declared function/gradient evaluation budget exhausted", False, len(history)
    best = min(history, key=lambda step: step["expectation"])
    gradient = engine.value_gradient(returned)[1]
    if success and np.linalg.norm(gradient, ord=np.inf) > settings["gradient_tolerance"]:
        raise ValueError("BFGS convergence contradicts the recomputed gradient")
    error = max(check_angles(cost, engine, angles) for angles in (initial, best["angles"], returned))
    return {"initial_angles": initial, "history": history, "best_angles": best["angles"],
            "best_expectation": best["expectation"], "returned_angles": returned,
            "returned_expectation": value, "returned_gradient": gradient.tolist(),
            "returned_gradient_infinity_norm": float(np.linalg.norm(gradient, ord=np.inf)),
            "optimizer_converged": success, "optimizer_status": status, "optimizer_message": message,
            "evaluations": len(history), "gradient_evaluations": len(history), "reported_nfev": nfev,
            "seconds": time.perf_counter() - started, "qiskit_check_max_error": error}


def read_protocol(output):
    output = Path(output)
    protocol = json.loads((output / "protocol.json").read_text())
    require(all(protocol[k] == v for k, v in SETTINGS.items()), "frozen BFGS settings changed")
    completed = (output / "completed.json").is_file()
    verify_preserved(ROOT, protocol["preserved_files"], completed=completed)
    for name, expected in protocol["source_sha256"].items():
        verify_source(ROOT, name, expected, output / (Path(name).name + ".txt"), completed=completed)
    return protocol


def plan(snapshot_root, cobyla, output):
    output, cobyla = Path(output), Path(cobyla)
    previous = verify_cobyla(snapshot_root, cobyla)
    first_protocol = json.loads((cobyla / "protocol.json").read_text())
    preserved = json.loads((cobyla / "preserved-files.json").read_text())
    for path in cobyla.rglob("*"):
        if path.is_file():
            logical = path.with_suffix("") if path.name.endswith(".json.gz") else path
            preserved[logical.relative_to(ROOT).as_posix()] = digest(logical)
    for name in first_protocol["source_sha256"]:
        preserved[name] = digest(ROOT / name)
    sources = ("research/robustness_bfgs.py", "research/artifacts.py")
    protocol = dict(SETTINGS, frozen_at_utc=datetime.now(timezone.utc).isoformat(),
                    baseline_directory=first_protocol["baseline_directory"],
                    cobyla_directory=cobyla.relative_to(ROOT).as_posix(),
                    cobyla_verification=previous, initial_starts=first_protocol["initial_starts"],
                    python=first_protocol["python"], versions=first_protocol["versions"],
                    preserved_files=preserved,
                    source_sha256={name: digest(ROOT / name) for name in sources})
    output.mkdir(parents=True, exist_ok=False)
    for name in sources:
        (output / (Path(name).name + ".txt")).write_bytes((ROOT / name).read_bytes())
    write_json(output / "protocol.json", protocol)
    return {"protocol_sha256": digest(output / "protocol.json"), "training_started": False,
            "planned_starts": 48, "maximum_function_gradient_evaluations": 96000,
            "planned_shots": 49152, "prior_cobyla_converged_starts": previous["formally_converged_starts"]}


def run(snapshot_root, output):
    output = Path(output)
    protocol = read_protocol(output)
    write_json(output / "started.json", {"at_utc": datetime.now(timezone.utc).isoformat(),
                                        "protocol_sha256": digest(output / "protocol.json")})
    records = []
    for case_name in CASES:
        case = adapt_case(snapshot_root, case_name.split("-")[0])
        _, cost, scores, error = verify_encoding(case, .5, case_name.endswith("-on"))
        minimum = min(scores.values())
        optimum = sorted(b for b, score in scores.items() if abs(score - minimum) <= 1e-12)
        for seed in protocol["training_seeds"]:
            started, attempts = time.perf_counter(), []
            for index, initial in enumerate(protocol["initial_starts"][str(seed)]):
                attempt = dict(train_start(cost, initial, protocol), start_index=index, case=case_name, seed=seed)
                write_json(output / f"{case_name}-{seed}-start-{index}.json", attempt)
                attempts.append(attempt)
            selected = select_attempt(attempts)
            sampled = sample_selected(cost, selected, seed, protocol["shots_per_run"])
            record = dict(study_id=protocol["study_id"], model_id=case["model_id"], case=case_name,
                          seed=seed, eta=.5, W_ref=case["W_ref"], data_sha256=case["source_sha256"],
                          execution_type="ideal_simulator", selected_start=selected["start_index"],
                          selected_optimizer_converged=selected["optimizer_converged"],
                          converged_starts=sum(a["optimizer_converged"] for a in attempts), total_starts=4,
                          expectation=selected["best_expectation"],
                          best_expectation_all_starts=min(a["best_expectation"] for a in attempts),
                          expectation_regret=selected["best_expectation"] - minimum,
                          optimizer_evaluations=sum(a["evaluations"] for a in attempts),
                          gradient_evaluations=sum(a["gradient_evaluations"] for a in attempts),
                          encoding_max_error=error, exact_minimum=minimum, complete_optimal_bits=optimum,
                          classical_substitution=False, seconds=time.perf_counter() - started, **sampled,
                          metrics=sample_metrics(sampled["counts"], scores, minimum, optimum))
            write_json(output / f"{case_name}-{seed}-qaoa_p1.json", record)
            records.append(record)
            print(f"BFGS {case_name} seed {seed}: {record['converged_starts']}/4 converged; E={record['expectation']:.9f}", flush=True)
    write_comparison(output, ROOT / protocol["baseline_directory"], records)
    read_protocol(output)
    write_json(output / "completed.json", {"at_utc": datetime.now(timezone.utc).isoformat(), "hardware_jobs_submitted": 0})


def verify(snapshot_root, output):
    output = Path(output)
    protocol = read_protocol(output)
    require(json.loads((output / "started.json").read_text())["protocol_sha256"] == digest(output / "protocol.json"), "protocol changed after training")
    require((output / "completed.json").is_file(), "incomplete BFGS study")
    baseline = ROOT / protocol["baseline_directory"]
    rows = json.loads((output / "comparison.json").read_text())
    require(len(rows) == 48 and len(trace_paths(output)) == 48, "missing runs")
    evaluations, converged, selected_converged, max_error = 0, 0, 0, 0.0
    comparisons = []
    for case_name in CASES:
        case = adapt_case(snapshot_root, case_name.split("-")[0])
        _, cost, scores, encoding_error = verify_encoding(case, .5, case_name.endswith("-on"))
        minimum = min(scores.values())
        optimum = sorted(b for b, value in scores.items() if abs(value - minimum) <= 1e-12)
        engine, new_values, old_values = DifferentiableP1(cost), [], []
        max_error = max(max_error, encoding_error)
        for seed in protocol["training_seeds"]:
            attempts = []
            require(protocol["initial_starts"][str(seed)] == starts_for_seed(seed, 4), "changed start schedule")
            for index, initial in enumerate(protocol["initial_starts"][str(seed)]):
                a = read_json(output / f"{case_name}-{seed}-start-{index}.json")
                require(a["initial_angles"] == initial and a["case"] == case_name and a["seed"] == seed and a["start_index"] == index, "attempt metadata mismatch")
                require(0 < len(a["history"]) == a["evaluations"] == a["gradient_evaluations"] == a["reported_nfev"] <= 2000, "evaluation accounting mismatch")
                require(a["history"][0]["angles"] == initial, "wrong optimizer start")
                for step in a["history"]:
                    value, gradient = engine.value_gradient(step["angles"])
                    require(close(value, step["expectation"]) and np.allclose(gradient, step["gradient"], rtol=0, atol=1e-12), "BFGS history mismatch")
                best = min(a["history"], key=lambda step: step["expectation"])
                require(a["best_angles"] == best["angles"] and a["best_expectation"] == best["expectation"], "wrong best checkpoint")
                returned, gradient = engine.value_gradient(a["returned_angles"])
                require(close(returned, a["returned_expectation"]) and np.allclose(gradient, a["returned_gradient"], rtol=0, atol=1e-12), "returned point mismatch")
                require(a["optimizer_converged"] == (a["optimizer_status"] == 0), "inconsistent convergence status")
                require(not a["optimizer_converged"] or np.linalg.norm(gradient, ord=np.inf) <= 1e-6, "false convergence claim")
                for angles in (initial, a["best_angles"], a["returned_angles"]):
                    max_error = max(max_error, check_angles(cost, engine, angles))
                # Independent central differences at the saved best point.
                angles = np.asarray(a["best_angles"])
                finite = [(engine.expectation(angles + np.eye(2)[i] * 1e-5) - engine.expectation(angles - np.eye(2)[i] * 1e-5)) / 2e-5 for i in range(2)]
                require(np.allclose(engine.value_gradient(angles)[1], finite, rtol=0, atol=1e-8), "analytic gradient differs from central differences")
                evaluations += a["evaluations"]
                converged += int(a["optimizer_converged"])
                attempts.append(a)
            selected = select_attempt(attempts)
            record = json.loads((output / f"{case_name}-{seed}-qaoa_p1.json").read_text())
            require(record["selected_start"] == selected["start_index"] and record["expectation"] == selected["best_expectation"]
                    and record["angles"] == dict(zip(("gamma", "beta"), selected["best_angles"]))
                    and record["selected_optimizer_converged"] == selected["optimizer_converged"], "selected record mismatch")
            require(record["model_id"] == case["model_id"] and record["data_sha256"] == case["source_sha256"]
                    and record["W_ref"] == case["W_ref"] and record["eta"] == .5
                    and record["case"] == case_name and record["seed"] == seed
                    and not record["classical_substitution"], "record provenance mismatch")
            require(record["complete_optimal_bits"] == optimum and close(record["exact_minimum"], minimum), "reference mismatch")
            require(record["optimizer_evaluations"] == record["gradient_evaluations"] == sum(a["evaluations"] for a in attempts)
                    and record["converged_starts"] == sum(a["optimizer_converged"] for a in attempts), "resource mismatch")
            require(close(record["expectation_regret"], record["expectation"] - minimum), "regret mismatch")
            measured = build_qaoa_circuit(cost, **record["angles"], measure=True)
            require(decode_counts(record["raw_counts"], measured) == record["counts"] and sum(record["counts"].values()) == record["shots"] == 4096, "shot/count mismatch")
            probabilities = Statevector.from_instruction(measured.remove_final_measurements(inplace=False)).probabilities()
            require(np.allclose(probabilities, engine.probabilities(selected["best_angles"]), rtol=0, atol=1e-12), "Qiskit probabilities mismatch")
            direct = math.fsum(float(p) * scores[format(i, "06b")[::-1]] for i, p in enumerate(probabilities))
            require(close(direct, record["expectation"]), "direct-score expectation mismatch")
            require(record["metrics"] == sample_metrics(record["counts"], scores, minimum, optimum), "metrics mismatch")
            for method in ("qaoa_p1_robustness", "qaoa_p1_v2", "uniform_v2", "annealing_best_of_independent_chains_v2"):
                matches = [r for r in rows if r["case"] == case_name and r["seed"] == seed and r["method"] == method]
                require(len(matches) == 1, "comparison row missing/duplicate")
                source = record if method == "qaoa_p1_robustness" else json.loads((baseline / f"{case_name}-{seed}-{method[:-3]}.json").read_text())
                require(all(matches[0][k] == v for k, v in source["metrics"].items()), "baseline/comparison metric changed")
                expected = record["expectation"] if method == "qaoa_p1_robustness" else source.get("training_and_sampling", {}).get("expectation")
                require(matches[0]["expectation"] == expected, "comparison expectation changed")
            selected_converged += int(record["selected_optimizer_converged"])
            new_values.append(record["expectation"])
            old_values.append(json.loads((baseline / f"{case_name}-{seed}-qaoa_p1.json").read_text())["training_and_sampling"]["expectation"])
        new_mean, old_mean = math.fsum(new_values) / 3, math.fsum(old_values) / 3
        comparisons.append({"case": case_name, "new_mean_expectation": new_mean, "v2_mean_expectation": old_mean,
                            "expectation_change": new_mean - old_mean,
                            "mean_expectation_no_worse_than_v2": new_mean <= old_mean + 1e-10})
    return {"status": "pass", "study": protocol["study_id"], "attempts_verified": 48,
            "selected_runs_verified": 12, "formally_converged_starts": converged,
            "formally_converged_selected_runs": selected_converged, "optimizer_evaluations": evaluations,
            "analytic_gradient_evaluations": evaluations, "qiskit_checkpoint_comparisons": 144,
            "central_difference_gradient_checks": 48, "maximum_numeric_discrepancy": max_error,
            "actual_new_qaoa_final_shots": 49152, "v2_and_cobyla_unchanged": True,
            "case_comparison": comparisons, "hardware_jobs_submitted": 0}


def recommend_bfgs(snapshot_root, output, verification):
    # The shared recommendation writer reads the COBYLA protocol. Pass the BFGS
    # protocol explicitly through a local implementation rather than changing it.
    output = Path(output)
    protocol = read_protocol(output)
    records = [json.loads(p.read_text()) for p in output.glob("priority-debris-on-*-qaoa_p1.json")]
    eligible = [r for r in records if r["selected_optimizer_converged"]]
    selected = min(eligible, key=lambda r: (r["expectation"], r["seed"])) if eligible else None
    baseline = ROOT / protocol["baseline_directory"]
    old = [json.loads(p.read_text()) for p in baseline.glob("priority-debris-on-*-qaoa_p1.json")]
    passed = (verification["status"] == "pass" and verification["formally_converged_selected_runs"] == 12
              and all(r["mean_expectation_no_worse_than_v2"] for r in verification["case_comparison"])
              and selected is not None and selected["expectation"] <= min(r["training_and_sampling"]["expectation"] for r in old) + 1e-10)
    if passed:
        _, cost, _, _ = verify_encoding(adapt_case(snapshot_root, "priority"), .5, True)
        gradient = DifferentiableP1(cost).value_gradient([selected["angles"]["gamma"], selected["angles"]["beta"]])[1]
        passed = bool(np.linalg.norm(gradient, ord=np.inf) <= 1e-6)
    report = {"status": "recommend_angles_for_fresh_preparation" if passed else "no_hardware_angle_recommendation",
              "gate_passed": passed, "study_id": protocol["study_id"], "model_id": protocol["model_id"],
              "case": "priority-debris-on", "eta": .5, "submission_authorized": False,
              "hardware_jobs_submitted": 0, "all_case_comparison_completed": True,
              "intended_backend": "ibm_fez, subject to fresh eligibility/calibration checks",
              "main_shots": 4096, "mapping_controls": 6, "shots_per_control": 32, "total_shots": 4288,
              "compiled_depth_two_qubit_gates_and_usage": "pending fresh compilation; old v2 proposal does not transfer",
              "comparison_scope": "optimizer robustness, not quantum advantage; BFGS was declared after observing COBYLA failures"}
    if passed:
        from qiskit import QuantumCircuit
        from quantum import verify_measurement_mapping
        _, cost, _, _ = verify_encoding(adapt_case(snapshot_root, "priority"), .5, True)
        circuit = build_qaoa_circuit(cost, **selected["angles"], measure=True)
        controls = []
        for i in range(6):
            control = QuantumCircuit(6, 6, name=f"event_mapping_{i}")
            control.x(i)
            control.measure(range(6), range(6))
            controls.append(control)
        for c in (circuit, *controls):
            verify_measurement_mapping(c, 6)
        with (output / "recommended-logical.qpy").open("xb") as stream:
            qpy.dump([circuit, *controls], stream)
        report.update({"selected_seed": selected["seed"], "selected_start": selected["selected_start"],
                       "angles": selected["angles"], "expectation": selected["expectation"],
                       "optimizer_converged": True, "data_sha256": selected["data_sha256"],
                       "training_record": f"priority-debris-on-{selected['seed']}-qaoa_p1.json",
                       "logical_qpy_sha256": digest(output / "recommended-logical.qpy"),
                       "logical_depth": circuit.depth(),
                       "logical_two_qubit_gates": sum(len(i.qubits) == 2 for i in circuit.data)})
    write_json(output / "hardware-angle-recommendation.json", report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("plan", "run", "verify"))
    parser.add_argument("--snapshot-root", type=Path, required=True)
    parser.add_argument("--cobyla", type=Path, default=ROOT / "results/responsibility-p1-robustness-20261115")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.phase == "plan":
        print(json.dumps(plan(args.snapshot_root, args.cobyla, args.output), indent=2))
    elif args.phase == "run":
        run(args.snapshot_root, args.output)
    else:
        report = verify(args.snapshot_root, args.output)
        write_json(args.output / "verification.json", report)
        recommend_bfgs(args.snapshot_root, args.output, report)
        print(json.dumps(report, indent=2))
