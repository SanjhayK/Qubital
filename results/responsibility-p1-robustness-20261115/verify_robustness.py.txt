"""Verify the complete robustness study before recommending hardware angles.

Local only. Rebuilds all model encodings and checks every training evaluation,
Qiskit circuit checkpoints, final counts, comparisons and preservation hashes.
"""

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit, qpy
from qiskit.quantum_info import Statevector

from quantum import build_qaoa_circuit, decode_counts, verify_measurement_mapping
from research.experiments import sample_metrics, verify_encoding, write_json
from research.robustness import (CASES, ROOT, P1State, check_angles, check_preservation,
                                 digest, read_protocol, select_attempt, starts_for_seed)
from research.socrates_gate import adapt_case


def require(condition, message):
    if not condition:
        raise ValueError(message)


def close(a, b):
    return math.isclose(a, b, rel_tol=0, abs_tol=1e-12)


def verify(snapshot_root, output):
    output = Path(output)
    protocol = read_protocol(output)
    baseline = ROOT / protocol["baseline_directory"]
    started = json.loads((output / "started.json").read_text())
    completed = json.loads((output / "completed.json").read_text())
    require(started["protocol_sha256"] == digest(output / "protocol.json"), "protocol changed after start")
    require(protocol["frozen_at_utc"] <= started["at_utc"] <= completed["at_utc"], "invalid study timestamps")
    rows = json.loads((output / "comparison.json").read_text())
    aggregate = json.loads((output / "aggregate.json").read_text())
    require(len(rows) == 48 and len(aggregate) == 16, "incomplete comparisons")
    summary, records = [], []
    total_evaluations, converged_starts, max_error = 0, 0, 0.0
    checkpoints = 0
    old_references = json.loads((baseline / "exact_references.json").read_text())
    for case_name in CASES:
        variant, background = case_name.split("-")[0], case_name.endswith("-on")
        case = adapt_case(snapshot_root, variant)
        _, cost, scores, encoding_error = verify_encoding(case, protocol["eta"], background)
        minimum = min(scores.values())
        optimum = sorted(b for b, score in scores.items() if abs(score - minimum) <= 1e-12)
        reference = next(r for r in old_references if r["weight_variant"] == variant and r["background"] == background)
        require(optimum == reference["optimal_bits"] and close(minimum, reference["minimum_score"]), "changed exact problem")
        require(case["source_sha256"] == reference["data_sha256"] and case["W_ref"] == reference["W_ref"], "changed data/normalization")
        max_error = max(max_error, encoding_error)
        engine = P1State(cost)
        for seed in protocol["training_seeds"]:
            initials = starts_for_seed(seed, protocol["starts_per_seed"])
            require(initials == protocol["initial_starts"][str(seed)], "initial schedule changed")
            attempts = []
            old = json.loads((baseline / f"{case_name}-{seed}-qaoa_p1.json").read_text())
            require(initials[0] == old["training_and_sampling"]["initial_angles"], "first start differs from v2")
            for index, initial in enumerate(initials):
                attempt = json.loads((output / f"{case_name}-{seed}-start-{index}.json").read_text())
                require(attempt["initial_angles"] == initial and attempt["start_index"] == index
                        and attempt["case"] == case_name and attempt["seed"] == seed, "attempt metadata mismatch")
                history = attempt["history"]
                require(0 < len(history) == attempt["evaluations"] == attempt["reported_nfev"]
                        <= protocol["max_evaluations_per_start"], "wrong evaluation accounting")
                require(history[0]["angles"] == initial, "optimizer did not start at declared angles")
                require(type(attempt["optimizer_converged"]) is bool and
                        attempt["optimizer_converged"] == (attempt["optimizer_status"] == 0), "inconsistent COBYLA convergence status")
                for step in history:
                    require(close(engine.expectation(step["angles"]), step["expectation"]), "training history changed")
                best = min(history, key=lambda step: step["expectation"])
                require(attempt["best_angles"] == best["angles"] and attempt["best_expectation"] == best["expectation"], "best checkpoint mismatch")
                require(close(engine.expectation(attempt["returned_angles"]), attempt["returned_expectation"]), "returned expectation mismatch")
                for angles in (initial, attempt["best_angles"], attempt["returned_angles"]):
                    max_error = max(max_error, check_angles(cost, engine, angles))
                    checkpoints += 1
                total_evaluations += len(history)
                converged_starts += int(attempt["optimizer_converged"])
                attempts.append(attempt)
            selected = select_attempt(attempts)
            record = json.loads((output / f"{case_name}-{seed}-qaoa_p1.json").read_text())
            require(record["selected_start"] == selected["start_index"] and
                    record["selected_optimizer_converged"] == selected["optimizer_converged"] and
                    record["expectation"] == selected["best_expectation"] and
                    record["angles"] == dict(zip(("gamma", "beta"), selected["best_angles"])), "selection mismatch")
            require(record["model_id"] == case["model_id"] and record["data_sha256"] == case["source_sha256"]
                    and record["case"] == case_name and record["seed"] == seed
                    and record["eta"] == .5 and record["W_ref"] == case["W_ref"]
                    and record["execution_type"] == "ideal_simulator" and not record["classical_substitution"], "record provenance mismatch")
            require(record["optimizer_evaluations"] == sum(a["evaluations"] for a in attempts)
                    and record["converged_starts"] == sum(a["optimizer_converged"] for a in attempts)
                    and record["total_starts"] == 4, "record resource accounting mismatch")
            require(record["complete_optimal_bits"] == optimum and close(record["exact_minimum"], minimum), "optimum mismatch")
            require(close(record["expectation_regret"], record["expectation"] - minimum), "expectation regret mismatch")
            measured = build_qaoa_circuit(cost, **record["angles"], measure=True)
            require(decode_counts(record["raw_counts"], measured) == record["counts"], "count decoding mismatch")
            require(sum(record["counts"].values()) == record["shots"] == 4096, "shot accounting mismatch")
            probabilities = Statevector.from_instruction(measured.remove_final_measurements(inplace=False)).probabilities()
            require(np.allclose(probabilities, engine.probabilities(selected["best_angles"]), rtol=0, atol=1e-12), "probability mismatch")
            expectation = math.fsum(float(p) * scores[format(i, "06b")[::-1]] for i, p in enumerate(probabilities))
            require(close(expectation, record["expectation"]), "direct-score circuit expectation mismatch")
            metrics = sample_metrics(record["counts"], scores, minimum, optimum)
            require(record["metrics"] == metrics, "sample metrics mismatch")
            for method in ("qaoa_p1_robustness", "qaoa_p1_v2", "uniform_v2", "annealing_best_of_independent_chains_v2"):
                matches = [row for row in rows if row["case"] == case_name and row["seed"] == seed and row["method"] == method]
                require(len(matches) == 1, "missing/duplicate comparison row")
                row = matches[0]
                source = record if method == "qaoa_p1_robustness" else json.loads((baseline / f"{case_name}-{seed}-{method[:-3]}.json").read_text())
                require(all(row[key] == value for key, value in source["metrics"].items()), "comparison differs from original metrics")
                expected = record["expectation"] if method == "qaoa_p1_robustness" else source.get("training_and_sampling", {}).get("expectation")
                require(row["expectation"] == expected, "comparison expectation mismatch")
            records.append(record)
        new = [r for r in records if r["case"] == case_name]
        old_rows = [row for row in rows if row["case"] == case_name and row["method"] == "qaoa_p1_v2"]
        new_mean = math.fsum(r["expectation"] for r in new) / 3
        old_mean = math.fsum(row["expectation"] for row in old_rows) / 3
        summary.append({"case": case_name, "new_mean_expectation": new_mean,
                        "v2_mean_expectation": old_mean, "expectation_change": new_mean - old_mean,
                        "mean_expectation_no_worse_than_v2": new_mean <= old_mean + 1e-10})
    for item in aggregate:
        selected = [row for row in rows if row["case"] == item["case"] and row["method"] == item["method"]]
        for key in ("complete_optimum_hit_probability", "absolute_regret", "expectation", "expectation_regret"):
            values = [row[key] for row in selected if row.get(key) is not None]
            expected = {"mean": math.fsum(values) / len(values), "min": min(values), "max": max(values)} if values else None
            require(item[key] == expected, "aggregate metric mismatch")
    require(len(list(output.glob("*-start-*.json"))) == 48 and len(records) == 12, "incomplete study")
    return {"status": "pass", "verified_at_utc": datetime.now(timezone.utc).isoformat(),
            "protocol_sha256": digest(output / "protocol.json"),
            "preserved_files": check_preservation(output), "v2_unchanged": True,
            "cases_verified": 4, "attempts_verified": 48, "selected_runs_verified": 12,
            "formally_converged_starts": converged_starts,
            "formally_converged_selected_runs": sum(r["selected_optimizer_converged"] for r in records),
            "optimizer_evaluations": total_evaluations, "qiskit_checkpoint_comparisons": checkpoints,
            "basis_encoding_comparisons": 256, "maximum_numeric_discrepancy": max_error,
            "actual_new_qaoa_final_shots": sum(r["shots"] for r in records),
            "case_comparison": summary, "hardware_jobs_submitted": 0}


def recommend(snapshot_root, output, verification):
    """Recommendation only after all-case verification; create local logical QPY."""
    output = Path(output)
    target = [json.loads(p.read_text()) for p in output.glob("priority-debris-on-*-qaoa_p1.json")]
    eligible = [r for r in target if r["selected_optimizer_converged"]]
    protocol = read_protocol(output)
    baseline = ROOT / protocol["baseline_directory"]
    old = [json.loads(p.read_text()) for p in baseline.glob("priority-debris-on-*-qaoa_p1.json")]
    selected = min(eligible, key=lambda r: (r["expectation"], r["seed"])) if eligible else None
    passed = (verification["status"] == "pass" and verification["formally_converged_selected_runs"] == 12
              and all(r["mean_expectation_no_worse_than_v2"] for r in verification["case_comparison"])
              and selected is not None and selected["expectation"] <= min(r["training_and_sampling"]["expectation"] for r in old) + 1e-10)
    report = {"status": "recommend_angles_for_fresh_preparation" if passed else "no_hardware_angle_recommendation",
              "model_id": protocol["model_id"], "case": "priority-debris-on", "eta": .5,
              "submission_authorized": False, "hardware_jobs_submitted": 0,
              "all_case_comparison_completed": True, "gate_passed": passed,
              "intended_backend": "ibm_fez, subject to fresh eligibility/calibration checks",
              "main_shots": 4096, "mapping_controls": 6, "shots_per_control": 32, "total_shots": 4288,
              "compiled_depth_two_qubit_gates_and_usage": "pending fresh compilation for these angles; old proposal values do not transfer",
              "old_v2_hardware_proposal": "preserved historical preparation, not the recommended current angles",
              "comparison_scope": "more optimization work than v2; within-dataset robustness, not quantum advantage"}
    if passed:
        case = adapt_case(snapshot_root, "priority")
        _, cost, _, _ = verify_encoding(case, .5, True)
        circuit = build_qaoa_circuit(cost, **selected["angles"], measure=True)
        circuit.name = "responsibility_confirmatory_priority_background_on"
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
                       "training_record_sha256": digest(output / f"priority-debris-on-{selected['seed']}-qaoa_p1.json"),
                       "logical_qpy_sha256": digest(output / "recommended-logical.qpy"),
                       "logical_depth": circuit.depth(),
                       "logical_two_qubit_gates": sum(len(i.qubits) == 2 for i in circuit.data)})
    write_json(output / "hardware-angle-recommendation.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-root", required=True, type=Path)
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--recommend", action="store_true")
    args = parser.parse_args()
    report = verify(args.snapshot_root, args.results)
    write_json(args.results / "verification.json", report)
    if args.recommend:
        recommend(args.snapshot_root, args.results, report)
    print(json.dumps(report, indent=2))
