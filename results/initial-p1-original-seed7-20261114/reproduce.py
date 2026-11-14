"""Reproduce this single verified initial run; not an experiment sweep or solver.

Run from the repository root with --output pointing to a NEW JSON file. Before
the foundation merges, --scorer-ref loads the real scorer directly from a pinned
Git object in memory. It never copies, merges, or modifies teammate-owned code.
"""

import argparse
import hashlib
import importlib
import json
import platform
from pathlib import Path
import subprocess
import sys
import types


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from quantum import (  # noqa: E402 - allow invocation from any working directory
    build_qubo,
    optimize_qaoa,
    qubo_to_ising,
    summarize_samples,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scorer-ref", help="real scorer Git ref, if not merged")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("choose a new output file; existing results are preserved")

    def git(*arguments):
        return subprocess.check_output(["git", *arguments], cwd=ROOT, text=True).strip()

    if args.scorer_ref:
        scorer_sha = git("rev-parse", "--verify", f"{args.scorer_ref}^{{commit}}")
        source = git("show", f"{scorer_sha}:scoring.py")
        scoring = types.ModuleType("scoring")
        scoring.__file__ = f"git:{scorer_sha}:scoring.py"
        exec(compile(source, scoring.__file__, "exec"), scoring.__dict__)
        sys.modules["scoring"] = scoring
    else:
        scoring = importlib.import_module("scoring")
        scorer_sha = git("log", "-1", "--format=%H", "--", "scoring.py")
    scenario_path = ROOT / "data/original.json"
    scenario = scoring.load_scenario(scenario_path)
    alpha = 0.25
    # Complete original alpha=.25 reference set, independently established by
    # the authoritative scorer acceptance tests. No classical solver is added.
    reference_optima = {"100011"}
    qubo = build_qubo(scenario, alpha)
    result = optimize_qaoa(
        qubo_to_ising(qubo), seed=7, shots=4096, maxiter=300, starts=4
    )
    result.update({
        "project": "Qubital", "scenario_id": scenario["scenario_id"], "alpha": alpha,
        "python_version": platform.python_version(),
        "scenario_sha256": hashlib.sha256(scenario_path.read_bytes()).hexdigest(),
        "quantum_source_sha256": hashlib.sha256((ROOT / "quantum.py").read_bytes()).hexdigest(),
        "base_commit": git("merge-base", "HEAD", "origin/main"),
        "scorer_provenance": {
            "source": "pinned Git object" if args.scorer_ref else "imported merged scoring.py",
            "commit": scorer_sha,
            "source_sha256": hashlib.sha256(
                source.encode() if args.scorer_ref else Path(scoring.__file__).read_bytes()
            ).hexdigest(),
            "loaded_from_task_checkout": not bool(args.scorer_ref),
        },
        "classical_reference": {
            "optimal_bits": sorted(reference_optima),
            "objective_score": scoring.evaluate_plan(scenario, "100011", alpha)["objective_score"],
            "provenance": "authoritative scorer exhaustive original-scenario acceptance check",
        },
        "metrics": summarize_samples(
            scenario, result["canonical_counts"], alpha, optimal_bits=reference_optima
        ),
        "verification": {
            "basis_states_per_case": 64,
            "alphas": [0, 0.25, 0.5, 1],
            "scenarios": ["original", "B2 unavailable", "A1 and B1 unavailable"],
            "requirement": "Run tests/test_quantum.py with this real scorer before accepting results",
            "pending": "Compare with teammate classical.py once available",
        },
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2, sort_keys=True, allow_nan=False)
        output.write("\n")
    print(json.dumps({"angles": result["angles"], "expectation": result["expectation"],
                      "metrics": result["metrics"]}, indent=2))


if __name__ == "__main__":
    main()
