"""Technical comparison artifacts for v2 and both local optimizer follow-ups."""

import argparse
import csv
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from research.experiments import write_json
from research.robustness import CASES, ROOT, digest


def make_report(cobyla, bfgs, output):
    cobyla, bfgs, output = Path(cobyla), Path(bfgs), Path(output)
    output.mkdir(parents=True, exist_ok=False)
    rows = json.loads((cobyla / "comparison.json").read_text())
    for row in rows:
        if row["method"] == "qaoa_p1_robustness":
            row["method"] = "qaoa_cobyla_2000"
    for row in json.loads((bfgs / "comparison.json").read_text()):
        if row["method"] == "qaoa_p1_robustness":
            rows.append(dict(row, method="qaoa_bfgs_analytic"))
    protocol = json.loads((cobyla / "protocol.json").read_text())
    baseline = ROOT / protocol["baseline_directory"]
    references = json.loads((baseline / "exact_references.json").read_text())
    for row in rows:
        ref = next(r for r in references if row["case"] == f"{r['weight_variant']}-debris-{'on' if r['background'] else 'off'}")
        row.update(exact_minimum=ref["minimum_score"], complete_optimal_bits=ref["optimal_bits"],
                   number_of_optima=ref["number_of_optima"], W_ref=ref["W_ref"], eta=.5,
                   model_id=protocol["model_id"])
    write_json(output / "comparison.json", rows)
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with (output / "comparison.csv").open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys, lineterminator="\n")
        writer.writeheader()
        writer.writerows({k: json.dumps(v) if isinstance(v, list) else v for k, v in row.items()} for row in rows)
    methods = [("uniform_v2", "Uniform (v2)", "#8a8a8a"),
               ("qaoa_p1_v2", "QAOA v2", "#82b8bd"),
               ("qaoa_cobyla_2000", "QAOA COBYLA multistart", "#377eab"),
               ("qaoa_bfgs_analytic", "QAOA BFGS multistart", "#237548"),
               ("annealing_best_of_independent_chains_v2", "Annealing chain-best (v2)", "#d67b31")]
    aggregate = []
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), layout="constrained")
    for offset, (method, label, color) in zip(np.arange(5) * .16 - .32, methods):
        for axis, metric in zip(axes, ("complete_optimum_hit_probability", "absolute_regret")):
            values = [[r[metric] for r in rows if r["case"] == case and r["method"] == method] for case in CASES]
            means = [math.fsum(v) / len(v) for v in values]
            axis.bar(np.arange(4) + offset, means, width=.15, color=color, label=label,
                     yerr=[[mean - min(v) for mean, v in zip(means, values)],
                           [max(v) - mean for mean, v in zip(means, values)]], capsize=2)
        for case in CASES:
            selected = [r for r in rows if r["case"] == case and r["method"] == method]
            item = {"case": case, "method": method, "seeds": len(selected)}
            for key in ("complete_optimum_hit_probability", "absolute_regret", "expectation", "expectation_regret"):
                values = [r[key] for r in selected if r.get(key) is not None]
                item[key] = {"mean": math.fsum(values) / len(values), "min": min(values), "max": max(values)} if values else None
            item["formally_converged_starts"] = sum(r["converged_starts"] or 0 for r in selected)
            item["total_starts"] = sum(r["total_starts"] or 0 for r in selected)
            item["selected_converged_runs"] = sum(r["optimizer_converged"] is True for r in selected)
            aggregate.append(item)
    for axis in axes:
        axis.set_xticks(np.arange(4), ["Unit\nbackground off", "Unit\nbackground on", "Priority\nbackground off", "Priority\nbackground on"])
        axis.grid(axis="y", alpha=.2)
        axis.set_axisbelow(True)
        axis.set_ylim(bottom=0)
    axes[0].set_ylim(0, 1.05)
    axes[0].set_ylabel("Probability of any tied exact optimum")
    axes[1].set_ylabel("Sampled mean J minus exact minimum")
    fig.legend(*axes[0].get_legend_handles_labels(), loc="outside upper center", ncol=3, fontsize=9,
               title="Qubital: all-case p=1 optimizer robustness (ideal six-qubit simulation)", title_fontsize=12)
    fig.supxlabel("4096 final samples per method/seed; whiskers show three-seed ranges, not confidence intervals.\n"
                  "v2: 0/12 starts converged; multistart COBYLA: 20/48; analytic BFGS: 48/48.\n"
                  "Optimization work, gradient access and simulator implementations differ; no speedup claim.", fontsize=9)
    fig.savefig(output / "comparison.png", dpi=180)
    plt.close(fig)
    write_json(output / "aggregate.json", aggregate)
    write_json(output / "provenance.json", {
        "renderer_sha256": digest(__file__),
        "input_sha256": {str(path.relative_to(ROOT)): digest(path) for path in
                          (cobyla / "comparison.json", cobyla / "verification.json",
                           bfgs / "comparison.json", bfgs / "verification.json")},
        "v2_baselines_reused_unchanged": True, "case_count": 4, "comparison_records": len(rows),
        "hardware_jobs_submitted": 0,
        "interpretation": "better optimization reliability does not imply quantum advantage or physical safety",
    })
    return aggregate


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cobyla", type=Path, default=ROOT / "results/responsibility-p1-robustness-20261115")
    parser.add_argument("--bfgs", type=Path, default=ROOT / "results/responsibility-p1-robustness-bfgs-20261115")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    make_report(args.cobyla, args.bfgs, args.output)
