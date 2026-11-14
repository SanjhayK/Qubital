"""Create one comparison figure and compact tables from recorded research runs."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def make_report(directory, output_directory=None):
    directory = Path(directory)
    output_directory = Path(output_directory) if output_directory is not None else directory
    if output_directory != directory:
        output_directory.mkdir(parents=True, exist_ok=False)
    if (output_directory / "comparison.csv").exists():
        raise ValueError("derived report exists; choose a new output directory")
    rows = json.loads((directory / "summary.json").read_text())
    for row in rows:
        detail = json.loads((directory / f"{row['case']}-{row['seed']}-{row['method']}.json").read_text())
        row["sampling_succeeded"] = detail.get("success", True)
        row["optimizer_converged"] = detail.get("optimizer_converged")
        row["training_status"] = detail.get("training_status", "not_applicable" if row["method"] != "qaoa_p1" else "failed_before_sampling")
    references = json.loads((directory / "exact_references.json").read_text())
    by_case = {f"{r['weight_variant']}-{'debris-on' if r['background'] else 'debris-off'}": r for r in references}
    for row in rows:
        detail = json.loads((directory / f"{row['case']}-{row['seed']}-{row['method']}.json").read_text())
        reference = by_case[row["case"]]
        row.update({key: detail[key] for key in ("model_id", "data_sha256", "eta", "W_ref", "execution_type")})
        row.update({"weight_variant": reference["weight_variant"], "background": reference["background"],
                    "complete_optimal_bits": reference["optimal_bits"], "exact_minimum_J": reference["minimum_score"],
                    "shots_or_returned_samples": sum(detail["counts"].values()),
                    "logical_depth": detail.get("logical_depth"),
                    "logical_two_qubit_gates": detail.get("logical_two_qubit_gates"),
                    "optimizer_evaluations": detail.get("optimizer_evaluations"),
                    "annealing_cached_queries": detail.get("cached_objective_queries")})
    (output_directory / "summary-with-status.json").write_text(json.dumps(rows, indent=2, allow_nan=False) + "\n")
    keys = ["model_id", "data_sha256", "case", "weight_variant", "background", "eta", "W_ref",
            "method", "execution_type", "seed", "shots_or_returned_samples", "sampling_succeeded", "optimizer_converged", "training_status",
            "logical_depth", "logical_two_qubit_gates", "optimizer_evaluations", "annealing_cached_queries",
            "complete_optimal_bits", "exact_minimum_J", "complete_optimum_hit_probability",
            "full_score_sample_mean", "absolute_regret", "best_actual_sampled_objective",
            "distinct_near_optimal_assignments", "distinct_assignments", "seconds"]
    with (output_directory / "comparison.csv").open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows({key: json.dumps(value) if isinstance(value, (list, dict)) else value
                          for key, value in row.items()} for row in rows)
    cases = [f"{r['weight_variant']}-{'debris-on' if r['background'] else 'debris-off'}" for r in references]
    methods = [("uniform", "Uniform", "#6b7280"),
               ("qaoa_p1", "QAOA p=1 (fixed budget)", "#167b83"),
               ("annealing_best_of_independent_chains", "Annealing chain-best", "#d67b31")]
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.3), layout="constrained")
    aggregate = []
    for offset, (method, label, color) in zip((-0.24, 0, 0.24), methods):
        for axis, metric in zip(axes, ("complete_optimum_hit_probability", "absolute_regret")):
            values = [[r[metric] for r in rows if r["case"] == case and r["method"] == method
                       and r["success"] and metric in r] for case in cases]
            means = [np.mean(v) if v else np.nan for v in values]
            lower = [mean - min(v) if v else 0 for mean, v in zip(means, values)]
            upper = [max(v) - mean if v else 0 for mean, v in zip(means, values)]
            axis.bar(np.arange(4) + offset, means, width=.23, color=color, label=label,
                     yerr=[lower, upper], capsize=3)
        for case in cases:
            selected = [r for r in rows if r["case"] == case and r["method"] == method]
            success = [r for r in selected if r["success"]]
            aggregate.append({"case": case, "method": method, "successful_seeds": len(success),
                "sampling_successful_seeds": len(success),
                "optimizer_converged_seeds": sum(r["optimizer_converged"] is True for r in selected)
                                            if method == "qaoa_p1" else None,
                "total_seeds": len(selected),
                **{metric: {"mean": float(np.mean([r[metric] for r in success])),
                            "min": min(r[metric] for r in success),
                            "max": max(r[metric] for r in success)} if success else None
                   for metric in ("complete_optimum_hit_probability", "absolute_regret",
                                  "full_score_sample_mean", "distinct_near_optimal_assignments")}})
    axes[0].set_ylabel("Probability of any exactly optimal assignment")
    axes[0].set_ylim(0, 1.05)
    axes[1].set_ylabel("Mean direct J − exact minimum J")
    axes[1].set_ylim(bottom=0)
    for axis in axes:
        axis.set_xticks(np.arange(4), [f"{r['weight_variant']}\nbackground {'on' if r['background'] else 'off'}\n{r['number_of_optima']} optima"
                                       for r in references])
        axis.grid(axis="y", alpha=.2)
        axis.set_axisbelow(True)
    axes[0].legend(loc="upper right", fontsize=8)
    fig.suptitle("Qubital: frozen six-event responsibility benchmark (ideal simulation)", fontsize=13)
    quantum_rows = [r for r in rows if r["method"] == "qaoa_p1"]
    converged = sum(r["optimizer_converged"] is True for r in quantum_rows)
    sampled = sum(r["sampling_succeeded"] for r in quantum_rows)
    fig.supxlabel("4096 returned samples/method/seed; three seeds; whiskers = seed range, not confidence intervals.\n"
                  "Annealing uses 4096 independent 32-step chains; computational work is not matched.\n"
                  f"QAOA: {sampled}/{len(quantum_rows)} sampling runs completed; {converged}/{len(quantum_rows)} optimizer starts converged.", fontsize=9)
    fig.savefig(output_directory / "comparison.png", dpi=180)
    fig.savefig(output_directory / "comparison.svg")
    svg = output_directory / "comparison.svg"
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
    plt.close(fig)
    (output_directory / "aggregate.json").write_text(json.dumps(aggregate, indent=2, allow_nan=False) + "\n")
    provenance = {"source_summary_sha256": hashlib.sha256((directory / "summary.json").read_bytes()).hexdigest(),
                  "renderer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  "figure_error_bars": "range of the three recorded seeds, not confidence intervals",
                  "sampling_success_is_not_optimizer_convergence": True}
    (output_directory / "rendering_provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    return aggregate


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output-directory", type=Path)
    args = parser.parse_args()
    make_report(args.directory, args.output_directory)
