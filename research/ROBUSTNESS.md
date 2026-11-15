# Local p=1 optimizer robustness follow-up

The frozen six-event responsibility model is unchanged. V2, its source archive,
all recorded results and both existing hardware proposals remain byte-identical.
The synthetic fuel/reserve model is also unchanged. These are local ideal
simulations, with no IBM authentication, hardware submission or allocation use.

## Protocol and why there are two follow-ups

Both follow-ups use all four unit/priority × background off/on cases, eta=.5,
root seeds 7/19/43, four deterministic starts per root seed, and one final
4096-shot sample per selected case/seed circuit. That is 48 attempts and 12
sampled circuits per follow-up. Initial angles are four successive draws from
`default_rng(seed)` on [0,2pi] × [0,pi]. The first start exactly matches v2.
All attempts run; none is discarded based on an unfavorable outcome.

1. **Larger-budget COBYLA:** at most 2000 evaluations/start, tolerance 1e-6,
   initial trust radius .5, unconstrained angles. Protocol SHA-256:
   `51697617bbfb24cd19deedcb9a96c7d3a8d4681a61cd0761de5c9edcf7d6b984`.
   It improved expectations but still hit MAXFUN on 28 of 48 starts.
2. **Analytic-gradient BFGS cross-check:** declared separately after observing
   those COBYLA failures, before any BFGS training. Same cases, physical initial
   angles and 2000-evaluation cap; maximum 2000 iterations/start; infinity-norm
   gradient tolerance 1e-6. Protocol SHA-256:
   `db7e44139f674b7ced7875cf49d592ffb0e22caaf869908f96854485f5a3478b`.
   All 48 starts converged. Returned gradients independently satisfy the stated
   tolerance; this is not a certificate of global angle optimality.

Selection is the lowest best-visited expectation among converged attempts,
with start index breaking exact ties. If none converged, the best visited
nonconverged result is sampled and explicitly labeled ineligible for hardware.
Both settings and every initial angle were written before training. Every
attempt retains its stop status, initial/returned/best angles, complete
evaluation history, time and accounting. BFGS also retains every analytic
gradient. This is a v2-informed, within-dataset confirmation, not independent
holdout validation. The second optimizer was not predeclared before COBYLA ran.

Training uses an efficient exact six-qubit statevector evolution: diagonal
Ising phases followed by RX mixers. It has no classical optimum lookup.
The cost/offset and ansatz are the same as Qiskit; all final measurements use
the actual Qiskit circuit on BasicSimulator. Different floating-point evaluation
paths can affect optimizer trajectories. Timing comparisons with v2 are not
controlled speedup experiments. BFGS additionally receives analytic derivatives,
so its evaluation count is not equivalent to COBYLA's scalar-oracle count.

## Observed comparison

Values are averages across three selected root-seed runs. E is full direct-J
expectation, including the constant offset. Hit rate recognizes every tied
optimum. Regret is the sampled mean J minus the exact minimum, not physical risk.

| Case | V2 E | COBYLA E | BFGS E | V2 hit | COBYLA hit | BFGS hit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Unit, background off | .236218431 | .230002136 | .229869675 | 39.77% | 50.70% | 52.40% |
| Unit, background on | .394254860 | .391996697 | .391996697 | 49.15% | 54.55% | 54.56% |
| Priority, background off | .484215834 | .483785292 | .483785292 | 4.69% | 4.81% | 4.81% |
| Priority, background on | .501711750 | .501610443 | .501610443 | 4.52% | 4.65% | 4.65% |

| Case | V2 sampled regret | COBYLA sampled regret | BFGS sampled regret | Best BFGS E |
| --- | ---: | ---: | ---: | ---: |
| Unit, background off | .017449697 | .011316935 | .011004130 | .229869675 |
| Unit, background on | .019301097 | .016877492 | .016874949 | .391996697 |
| Priority, background off | .083490595 | .083275419 | .083269118 | .483785292 |
| Priority, background on | .079089505 | .079194557 | .079194557 | .501610443 |

V2 had 0/12 formally converged starts. Larger-budget COBYLA had 20/48 converged
starts and 8/12 selected runs from converged attempts. BFGS had 48/48 and 12/12.
Across selected seeds, BFGS expectations differ by less than 9e-14 within each
case. This indicates consistency of the observed local solutions, not a proof
that other angle regions cannot be better.

The priority/background-on sampled regret is slightly **worse** than v2 despite
its lower exact expectation. Weighted-case changes are small; no significance
claim is made. Finite-shot metrics must remain separate from exact expectations.
The main improvement is reliable convergence, with the largest score/hit-rate
improvement in the unit/background-off case.

Exact optimum sets are unchanged: 15/6/1/1 optima in table order; the weighted
optimum remains `000010`. Exact enumeration, uniform sampling and independent
annealing chain-best outputs are reused from verified v2 records. Uniform mean
hits remain 23.15/9.55/1.60/1.60%; annealing remains
100/100/39.28/36.78%. Annealing has better optimum-hit rates here and uses a
different, larger cached-query budget. Enumeration already supplies all 64
assignments. No quantum advantage, physical-safety or unique-diversity claim is
supported. All free assignments are structurally valid by construction.

## Resources and verification

- COBYLA: 85,340 optimizer expectation evaluations; 49,152 final simulator shots;
  about 117.13 s summed training/sampling time, excluding independent verification.
- BFGS: 910 joint expectation/analytic-gradient evaluations; 49,152 final
  simulator shots; about 1.38 s summed training/sampling time, excluding
  independent verification. These timings are not hardware costs or speedups.
- Added follow-ups total: 86,250 optimizer expectation calls, of which 910 also
  produce gradients, and 98,304 final simulator shots. V1/v2 resource history is
  retained separately and is not erased by these totals.
- Each follow-up independently rechecks 256 direct/QUBO/Ising basis scores and
  144 initial/best/returned Qiskit expectation checkpoints. Maximum discrepancy
  is 4.44e-16. All 12 selected full probability distributions and count decoders
  are checked against Qiskit. Every training-history entry is recomputed.
- BFGS analytic gradients additionally pass central-difference checks at all
  48 best points and generic one-, two- and six-qubit test cases.
- Preservation manifests cover the original 146 tracked files and then the
  completed COBYLA follow-up. Frozen source files and input hashes are verified.
- Full tests with the private frozen dataset: **219 collected, 219 passed,
  0 failed, 0 skipped** in both the core and IBM SDK environments. The SDK run
  reports 35 Samplomatic beta / IBM transpiler deprecation warnings. No package
  upgrade was required. Details are in the separate execution audit.

## Hardware angles: recommendation only

The all-case gate passed for BFGS, not for the COBYLA follow-up. Only after that
comparison and verification, the fixed priority/background-on target selected
seed 19/start 1 by the lowest recorded expectation among converged selected
seeds. Differences between these seeds are at numerical precision; seed choice
is not evidence of a meaningful performance difference.

- gamma = `4.91701540321722`
- beta = `-0.3713096130814176`
- Exact full expectation = `0.5016104432556737`
- Intended backend: ibm_fez, subject to fresh eligibility/calibration checks.
- Proposed sampling: 4096 main shots + six 32-shot mapping controls = 4288 shots.
- Saved logical circuit: six qubits, depth 13, 15 two-qubit gates.

`recommended-logical.qpy` and `hardware-angle-recommendation.json` are in the
BFGS result directory. They supersede the earlier v2 angles as the recommendation,
while leaving the earlier artifacts intact. **Fresh device compilation, layout
checks and usage estimates remain pending.** Old compiled depths/gate counts
and usage estimates must not be transferred to these angles. No job is
authorized or submitted, and no new on-device result is claimed.

## Reproduce without overwriting saved runs

Use the existing pinned environment; no packages were added or upgraded. Replace
`/path/to/socrates_snapshot` with the private extracted data directory.

```sh
python -m research.robustness plan --snapshot-root /path/to/socrates_snapshot --output /tmp/qubital-cobyla-new
python -m research.robustness run --snapshot-root /path/to/socrates_snapshot --output /tmp/qubital-cobyla-new
python -m research.verify_robustness --snapshot-root /path/to/socrates_snapshot --results /tmp/qubital-cobyla-new --recommend

python -m research.robustness_bfgs plan --snapshot-root /path/to/socrates_snapshot --cobyla /path/inside/repo/to/verified-cobyla --output /tmp/qubital-bfgs-new
python -m research.robustness_bfgs run --snapshot-root /path/to/socrates_snapshot --output /tmp/qubital-bfgs-new
python -m research.robustness_bfgs verify --snapshot-root /path/to/socrates_snapshot --output /tmp/qubital-bfgs-new

QUBITAL_SOCRATES_DIR=/path/to/socrates_snapshot python -m pytest -ra
```

The BFGS preservation manifest references a completed COBYLA directory inside
the repository. Its default is the committed verified follow-up. A newly created
COBYLA run can be used instead if placed inside the repository. The comparison
figure, seed-level CSV/JSON, complete optimum references and resource records are
under `results/responsibility-p1-robustness-comparison-20261115/` and the two
separate run directories. No raw source package is committed.
