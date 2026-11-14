"""Independently verify recorded responsibility-study outputs; no IBM/network calls."""

import argparse
import hashlib
import json
import math
from pathlib import Path

from qiskit.quantum_info import Statevector

from quantum import build_qaoa_circuit, decode_counts
from research.experiments import sample_metrics, verify_encoding
from research.socrates_gate import adapt_case


def verify(snapshot_root, directory):
    directory = Path(directory)
    root = Path(__file__).resolve().parents[1]
    protocol = json.loads((directory / "protocol.json").read_text())
    for name, digest in protocol["source_sha256"].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"recorded source changed: {name}")
    if hashlib.sha256((root / "research/experiments.py").read_bytes()).hexdigest() != protocol["runner_sha256"]:
        raise ValueError("recorded experiment runner changed")
    references = json.loads((directory / "exact_references.json").read_text())
    checked, shots, quantum_shots, evaluations, maximum_error = 0, 0, 0, 0, 0.0
    converged, method_runs = 0, {}
    quantum_seconds, annealing_queries = 0.0, 0
    for reference in references:
        variant, background = reference["weight_variant"], reference["background"]
        case = adapt_case(snapshot_root, variant)
        _, cost, scores, error = verify_encoding(case, .5, background)
        maximum_error = max(maximum_error, error)
        minimum = min(scores.values())
        optimum = sorted(b for b, value in scores.items() if abs(value - minimum) <= 1e-12)
        assert reference["optimal_bits"] == optimum
        assert math.isclose(reference["minimum_score"], minimum, rel_tol=0, abs_tol=1e-12)
        case_name = f"{variant}-{'debris-on' if background else 'debris-off'}"
        for seed in protocol["training_seeds"]:
            for method in ("uniform", "annealing_best_of_independent_chains", "qaoa_p1"):
                detail = json.loads((directory / f"{case_name}-{seed}-{method}.json").read_text())
                assert detail["model_id"] == "qubital.responsibility.v1"
                assert detail["case"] == case_name and detail["seed"] == seed
                counts = detail["counts"]
                assert sum(counts.values()) == 4096
                actual = sample_metrics(counts, scores, minimum, optimum)
                for key, value in actual.items():
                    saved = detail["metrics"][key]
                    if isinstance(value, float):
                        assert math.isclose(value, saved, rel_tol=0, abs_tol=1e-12), key
                    else:
                        assert value == saved, key
                if method == "qaoa_p1":
                    trained = detail["training_and_sampling"]
                    assert trained["sampling_succeeded"] and not trained["classical_substitution"]
                    history = trained["history"]
                    assert len(history) == detail["optimizer_evaluations"] <= 200
                    best = min(history, key=lambda row: row["expectation"])
                    assert trained["angles"] == dict(zip(("gamma", "beta"), best["angles"]))
                    state = Statevector.from_instruction(build_qaoa_circuit(cost, **trained["angles"]))
                    direct_expectation = math.fsum(
                        float(probability) * scores[format(i, "06b")[::-1]]
                        for i, probability in enumerate(state.probabilities())
                    )
                    assert math.isclose(trained["expectation"], direct_expectation, rel_tol=0, abs_tol=1e-12)
                    measured = build_qaoa_circuit(cost, **trained["angles"], measure=True)
                    assert decode_counts(trained["raw_counts"], measured) == counts
                    assert trained["optimizer_converged"] == detail["optimizer_converged"]
                    assert (trained["training_status"] == "converged") == trained["optimizer_converged"]
                    evaluations += len(history)
                    converged += int(trained["optimizer_converged"])
                    quantum_seconds += detail["seconds"]
                    quantum_shots += sum(counts.values())
                elif method == "annealing_best_of_independent_chains":
                    assert detail["cached_objective_queries"] == 4096 * 33
                    annealing_queries += detail["cached_objective_queries"]
                checked += 1
                shots += sum(counts.values())
                method_runs[method] = method_runs.get(method, 0) + 1
    return {"status": "pass", "recorded_method_runs_verified": checked,
            "method_runs": method_runs, "total_returned_samples": shots,
            "actual_ideal_qaoa_final_shots": quantum_shots,
            "quantum_optimizer_expectation_evaluations": evaluations,
            "quantum_optimizer_converged_runs": converged,
            "quantum_training_and_sampling_seconds_sum": quantum_seconds,
            "annealing_cached_score_queries": annealing_queries,
            "new_model_basis_state_comparisons": 256,
            "maximum_direct_qubo_ising_discrepancy": maximum_error,
            "historical_pilot": "v1 retains 12 convergence-gated MAXFUN failures with no quantum samples",
            "hardware_jobs_submitted": 0,
            "scope": "arithmetic/encoding/record QA; not validation of orbital or maneuver safety"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-root", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.snapshot_root, args.results)
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(report, indent=2, allow_nan=False))
