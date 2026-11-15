# Qubital: frozen-data responsibility research

For the latest all-case optimizer checks and current logical hardware-angle
recommendation, read [ROBUSTNESS.md](ROBUSTNESS.md). The v2 experiment described
below remains the original fixed-budget reference, with unchanged records.

This is a separate **conditional responsibility-assignment** benchmark. It leaves
`scoring.py`, `classical.py`, `data/original.json`, `quantum.py`, and their existing
tests/results unchanged. The original fuel/reserve example remains synthetic.

## Question, ownership, and model

How well does shallow QAOA sample low-burden assignments on a frozen six-event
screening case compared with exact enumeration, uniform sampling, and a classical
Metropolis baseline? Exact enumeration already provides the full 64-assignment
menu; neither a diverse menu nor these small timings establishes quantum advantage.

Kartikeya Pendem owns these new research modules/tests/results and the quantum
adapter. Sanjhay owns the existing scenario/scoring/classical files and their
tests, independent source review, final slides/simple plots, and any existing UI.
The new figure and presentation notes are research handoff material for review;
no teammate-owned slide or UI file was edited.

`model_id = qubital.responsibility.v1`. Free bit `y_e=1` assigns OneWeb; `0`
assigns Starlink. In particular **`000000` means all Starlink**, whereas in the
old synthetic action model it selected no actions. Each response is conditional:
no bitstring proves a jointly feasible or safe maneuver sequence.

Every fleet and satellite burden is fixed background plus assigned event weight.
The authoritative new scorer is `research.responsibility.evaluate_assignment`:

```text
J(y) = [(1-eta) sum_fleet B_fleet(y)^2 + eta sum_satellite B_satellite(y)^2] / W_ref^2
```

Each burden is affine `a + sum b_i*y_i`; expand the square using `y_i²=y_i`,
retaining its constant and every cross term. The new QUBO reuses only the generic
QUBO/Ising/circuit helpers, not the old scorer or coverage encoding. Fixed choices
retain their burden; neither allowed side means infeasible. All-fixed cases are
evaluated once without constructing a zero-qubit QAOA problem.

The main comparison fixes `eta=.5`. Exact references also cover 0 and 1. Unit
weights are 1; priority weights are `MAX_PROB / max(MAX_PROB in the active six)`.
Background uses the **same active-case scale**, without clamping it. These are
modeled workload/priority units, never fuel, delta-v, or true expected collision
loss. `W_ref` includes all six event weights and the two aligned background loads
once, and is frozen across background off/on: **8.0 unit**, **1.9611673672143677
priority**. It is not double-counted across fleet and satellite terms.

## Data gate and private source

The immutable input is the user's `Qubital_SOCRATES_2026-11-14.zip`, extracted
locally. Raw data and selected source-row CSVs are **not committed or published**.
No redistribution license is inferred from public availability. Credit
**CelesTrak / T. S. Kelso** for SOCRATES and SATCAT data.

- Raw source: https://celestrak.org/SOCRATES/sort-minRange.csv
- Frozen retrieval/known-available cutoff: `2026-11-14T21:40:05.826487+00:00`.
- SHA-256: `53f6fa639083579e65921cd3058ec2370f537eecb05d77398ec9d0989e22edec`.
- Verified 22,493,166 bytes and 198,115 rows; no missing/nonfinite numeric cells or
  canonical pair-plus-TCA duplicates.
- 17 OneWeb–Starlink rows; six already past and one additional row inside the
  **modeled**, not official, six-hour lead rule; ten eligible, then earliest six
  selected by TCA/IDs before solver outcomes.
- Symmetric DEB/R/B-name candidate discovery across all seven participating
  satellites found two aligned, SATCAT-confirmed debris events, both OneWeb.
  Five full-future OneWeb candidates exist, but only two fit this case's end time.
- The shared-OneWeb, different-partner pair 2.844 seconds apart remains two
  events. Its possible physical coupling is omitted, not silently deduplicated.

Gate completion `2026-11-14T22:39:19.905150+00:00` was within 20 minutes of the
task start. The supplied offline verifier was reviewed before execution. The
independent gate checks all source fields, hashes, time filters, types, joins,
denominators, and the supplied filtered slices. See
`results/research-gate-20261114/gate-audit.json` for per-file digests, UTC cutoffs,
the data dictionary, and known limitations.

This is a **retrospectively validated screening-data benchmark**, not a prospective
operational claim. Most SATCAT retrievals occurred after the raw cutoff; one
catalog response has no recorded retrieval-completion time. Filesystem mtime is
not substituted. No inference is made from “Data current as of” or a server clock.
The catalogue is not a complete inventory of threats or non-maneuverable payloads.
The checked OneWeb `OWNER=UK` is a country code, not a company; active status does
not establish maneuver capability. Both active responses are explicitly assumed
available for this conditional study.

## Reproduce offline

Use the existing Python 3.12 quantum environment. Matplotlib 3.10.8 was already
installed; no working dependencies were upgraded. Optional plotting pins are in
`requirements-research.txt`. No IBM key is required by the data/model/experiment
scripts, and none of those scripts imports the Runtime service.

```sh
# Point this scoped test variable at the extracted private socrates_snapshot folder.
QUBITAL_SOCRATES_DIR=/path/to/socrates_snapshot python -m pytest -ra

python -m research.experiments --snapshot-root /path/to/socrates_snapshot \
  --output /tmp/qubital-new-research-run
MPLCONFIGDIR=/tmp/qubital-mpl python -m research.report /tmp/qubital-new-research-run
python -m research.verify_results --snapshot-root /path/to/socrates_snapshot \
  --results /tmp/qubital-new-research-run --output /tmp/qubital-new-verification.json
```

Each run directory must be new; raw run JSON files are never overwritten. Without
the private snapshot, explicit data-integration skips are not passing data checks.
All 200 core/data/research tests passed in the executed environment before the
additional hardware-layout tests; final counts are recorded in the execution audit.

## Completed experiments and failure handling

`results/responsibility-p1-20261114-v2/` is the original fixed-budget result set: p=1, seeds
7/19/43, one start each, 200 quantum-expectation evaluations, and 4096 final shots
per case/seed. Four cases: unit/priority crossed with background off/on.
Training uses exact six-qubit statevectors, not shot-based expectation estimates.
Keep this distinct from final sampled counts and from proposed hardware execution.

The initial strict-convergence pilot in `...-v1/` exhausted all 12 budgets and
produced **no quantum samples**. It is retained. Version 2 is an explicitly
**post-pilot stopping-policy revision**, not a preregistration made before any
results: identical data, weights, seeds, and evaluation budget, but it samples
the best quantum angles actually visited at the budget limit. **0/12 starts
formally converged; 12/12 sampling runs completed.** No classical answers or
old synthetic counts were substituted. Detailed traces, stop messages, actual
calls, raw counts, and seed spread are preserved. Read `summary-with-status.json`
and `comparison.csv` for both sampling and convergence flags; the earlier basic
`summary.json` success field describes sampling, not optimizer convergence.

Uniform sampling and QAOA return 4096 assignments per seed. The annealing menu
adapts the Metropolis flip/cooling method in Sanjhay's `classical.py` to the same
new-model scorer: 4096 separately initialized 32-step chains, each returning its
best visited plan. It is not a stationary thermal distribution. Preprocessing
uses all 64 direct scores, shared with the exact reference; each annealing seed
then makes 135,168 cached queries. Sample budgets match; computation does not.
Lexicographic best-plan tie-breaking can reduce annealing's tied-menu diversity.

Near-optimal means **direct J <= exact minimum J + .02**, declared before the
pilot. Complete tied optimum sets use absolute tolerance `1e-12`. Relative gaps
use full direct J including constants, and are omitted for zero/flat objectives.
All free assignments are valid by construction: 100% validity is neither improved
quantum performance nor physical safety. Original synthetic counts are never
rescored under this model.

Read `RESULTS.md` for the preserved v2 findings and `ROBUSTNESS.md` for the
separate follow-ups. The reproducible Python scripts do not require a notebook.

## Historical hardware proposals and completed execution

The verified BFGS fixed-angle case has now run on ibm_fez as job
`dbsgu4habdes73fr5530`. See `results/responsibility-hardware-20261115/` for the
actual circuits, counts, decoder/control checks, usage and paired ideal analysis.
This is hardware sampling, not hardware angle training. The older proposals
below remain historical and were not used with old angles for this job.

The historical v2 preparation used `research.hardware_plan` to recompile a new-model priority/background-on circuit
from newly trained seed-7 angles. It did not reuse original-model angles or count
files. The separate proposal uses ibm_fez, one 4096-shot QAOA circuit and six
32-shot mapping controls on the same final physical qubits, 4288 shots total.
That v2 ISA QAOA has depth 142 and 54 CZ gates. Its one-subjob timing estimate
is about .0516 standard-QPU RU; the quick heuristic gives .0583 RU (one subjob)
or .2583 RU (seven). These are scenarios, not guaranteed bounds or billing quotes.
The retained v2 artifact is `results/responsibility-hardware-proposal-20261114-matched/`;
its 4096 main shots match the recorded ideal seed-7 comparison. The earlier
`...-20261114/` 1024-main-shot candidate is retained as superseded preparation,
not a hardware result or the current approval target. Both are superseded as
angle recommendations by the verified BFGS follow-up. Its new logical circuits
are in `results/responsibility-p1-robustness-bfgs-20261115/`. Fresh compilation
and layout checks were subsequently completed for the actual hardware run.
Metadata reads and local transpilation do not constitute a hardware result.
No 156-wire statevector is simulated. These historical proposal steps submitted
no job; subsequent execution used the user's separate explicit authorization.

The optional read-only proposal script needs the already configured Runtime
environment and secure settings; it never saves an account or logs key/CRN values.
The main research reproduction does not need it. Additional jobs require their
own authorization; result retrieval never resubmits a job.

The same preparation script now accepts the verified BFGS results through
`--runs results/responsibility-p1-robustness-bfgs-20261115`. It rechecks all four
cases before selecting the target and records the actual selected seed. This
path has local selection tests and was used for the completed IBM compilation.

## Sources and access

- [SOCRATES field definitions](https://celestrak.org/SOCRATES/socrates-format.php):
  UTC TCA; km ranges/dilution, km/s speed, days DSE; conservative MAX_PROB construction.
- [SATCAT format](https://celestrak.org/satcat/satcat-format.php) and
  [status](https://celestrak.org/satcat/status.php): type/identity joins, ownership,
  and limits of status-based capability inference.
- [CelesTrak use policy](https://celestrak.org/usage-policy.php): cache, respect
  update cadence, stop automated requests on non-200 responses.
- [IBM usage estimates](https://quantum.cloud.ibm.com/docs/en/ibm-quantum-compute/estimate-job-run-time)
  and [RU definitions](https://quantum.cloud.ibm.com/docs/en/ibm-quantum-platform/plans-overview).

The repository is private. Judge access, reuse rights for raw redistribution,
required organizer disclosures, and actual submission confirmation are not
verified. The supplied Devpost rules URL was attempted read-only but unavailable
through the web tool and environment proxy; no site changes/submission were made.
Do not change visibility automatically. Follow the conservative user-supplied
deadlines: Sat Nov 14 9 PM challenge, Sun Nov 15 8 AM main submission, and
9:30–10:30 AM presentations, all America/New_York. An indexed official event-page
snippet conflicted on the challenge time; it is insufficient to override these.
