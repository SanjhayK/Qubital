# Qubital research results — completed local study

Kartikeya Pendem and Sanjhay. Model `qubital.responsibility.v1`; frozen screening data, explicitly modeled workload, ideal six-qubit simulation. No real burns, noise experiment, or hardware execution is claimed.

## Main result

Fixed-budget p=1 QAOA improved optimum hit rates and direct-score regret versus uniform sampling in all four cases. The larger-query-budget annealing chain-best baseline performed better. Exact enumeration already provides the complete menu. These results do not establish a quantum advantage.

All 12 QAOA starts exhausted 200 evaluations: 0 formally converged, but all 12 produced genuine 4096-shot fixed-angle samples. The v1 strict-convergence pilot produced no quantum samples and remains archived; v2 is a disclosed post-pilot stopping-policy revision. Weights, seeds, case, and evaluation limit were unchanged.

## Complete optimum references and sampled hit rates

Hit rates below are averages across seeds 7,19,43; each method returns 4096 assignments/seed. They recognize every tied optimum. Different rows have different objectives/optimum-set sizes, so percentages are not directly comparable measures of case difficulty.

| Case | Exact minimum J | Complete optima | Uniform hit | QAOA hit (seed range) | Annealing hit | QAOA mean regret |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| unit-debris-off | 0.218750000 | 15 | 23.15% | 39.77% (38.72–40.38%) | 100.00% | 0.017450 |
| unit-debris-on | 0.375000000 | 6 | 9.55% | 49.15% (48.49–49.76%) | 100.00% | 0.019301 |
| priority-debris-off | 0.400980032 | 1 | 1.60% | 4.69% (4.05–5.52%) | 39.28% | 0.083491 |
| priority-debris-on | 0.422804808 | 1 | 1.60% | 4.52% (4.05–4.86%) | 36.78% | 0.079090 |

The priority optimum is `000010` both with and without aligned debris. This assigns the fifth selected event to OneWeb and the other five to Starlink. No positive debris-effect story is forced. Unit optimum counts change from 15 to 6; fleet-only eta0 unit control has 20 ties.

Near-optimal was fixed at `J <= J_min + .02`. Exact near-menu sizes are35,7,2,1 in table order. Uniform and QAOA both recovered the full near-optimal menu for every seed. There is no observed quantum menu-diversity benefit over uniform sampling here. Annealing endpoints concentrate on best plans; its tie-breaking and best-of-chain selection explain reduced diversity, not uniquely quantum alternatives.

## Interpretation and resources

- Full direct J includes the QUBO/Ising constant offset; primary gaps are absolute regret. Relative gaps are omitted for zero/flat objectives.
- All free assignments are structurally valid. A 100% validity rate is not an improvement over the original synthetic study and does not establish physical safety.
- Exact reference: 64 direct-score values/case; all 256 real state/model comparisons passed with maximum error 3.33e-16. The supplied preliminary sanity calculations were independently reproduced.
- QAOA: 2400 ideal expectation evaluations in v2, 49152 final simulator shots, and about 131.93 s summed training/sampling wall time on this machine. Each six-qubit logical circuit has 15 RZZ gates; actual per-run depth/gates are saved. Training expectations are exact statevectors, not sampled estimates.
- Annealing: 4096 independently initialized 32-step chains per case/seed, each returning its best visited plan. Total 1,622,016 cached score queries plus shared 64-value preprocessing/case; about 11.58 s recorded wall time. These are independent chain-best outputs, not correlated within-chain samples or a stationary distribution.
- Uniform: 49152 returned assignments overall, about 0.93 s recorded wall time. Sample counts match; optimization/preprocessing/compute budgets do not. These small wall times are not a fair speedup benchmark.
- The v1 pilot used another 2400 optimizer expectation evaluations plus 12 reporting calls and no quantum final shots. It is not hidden from the resource history.
- No p2, noise, mitigation, or on-device optimization was added. Prior original-model angles/counts were not reused or rescored.

## Presentation assets

- `../results/responsibility-p1-20261114-v2/final-report/comparison.png` and `.svg`: final figure with explicit convergence status.
- `../results/responsibility-p1-20261114-v2/final-report/comparison.csv`: seed-level results, sample-success and optimizer-convergence fields.
- `../results/responsibility-p1-20261114-v2/verification.json`: independently checked records and resource totals.
- `../results/responsibility-p1-20261114-v2/exact_references.json`: complete tied optimum sets and fixed normalizers.
- `../results/responsibility-p1-20261114-v2/eta_exact_references.json` and `fixed_response_checks.json`: cheap sensitivity and refusal references. Refusal may leave a deterministic assignment; neither side allowed is infeasible, never a zero-qubit quantum result.

## Strongest objection and a disproof test

This is a tiny weighted partitioning benchmark on one repeated OneWeb satellite versus six Starlink partners, not an operational maneuver planner or fleet-wide burden estimate. The strongest classical explanation is sufficient: exact enumeration solves the entire instance immediately, and a simple larger-query annealing menu is better at hitting optima. A disproof test for any claimed quantum benefit is the matched-sample uniform/independent-chain comparison already provided. The observed results support verification and a limited sampling improvement over uniform—not superiority over classical optimization.

## Hardware proposal, not a result

New-model priority/debris-on seed 7 was chosen by lowest observed quantum expectation across all three seeds. Its newly compiled ibm_fez proposal has 4096 QAOA shots plus 6×32 mapping-control shots, 4288 total; depth 142 and 54 CZ gates. New angles gamma 4.8501879357649536, beta 2.7686026999184037 differ from the old synthetic model. Estimated one-subjob duration model .0516 RU; heuristic .0583 RU (one subjob) or .2583 RU (seven). No job is authorized/submitted. The read-only instance history returned no accessible jobs in its 20-record query. Calibration, queue, and usage snapshots can change before a later approved submission.
