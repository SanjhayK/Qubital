# Qubital quantum core

This milestone independently encodes the shared synthetic maneuver model as a
QUBO and an Ising operator, then runs one-layer QAOA on an ideal simulator. It
does not simulate orbital trajectories or establish physical safety or speedup.

## Environment and API

There were no dependency files, `AGENTS.md`, or `HACKATHON-TOOLS.md` on the
inspected main commit `b1ffa2c8e83b09c95b618c65cadac32fe4e6a5b7`. The new
`AGENTS.md` records development guidelines and the model contract.
`requirements-quantum.txt` is separate from the shared project configuration and
pins the small tested dependency set. Python 3.12.14, Qiskit 2.2.3, NumPy 2.3.5, SciPy 1.17.0, and
pytest 8.4.2 were used. NumPy/SciPy were already installed; Qiskit/pytest and their
missing dependencies were installed in a virtual environment. Aer, algorithms,
optimization add-ons, and hardware credentials are unnecessary.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-quantum.txt
.venv/bin/python -m pytest -q -ra tests/test_quantum.py
```

- `build_qubo(scenario, alpha=None)` returns the polynomial with each pair once:
  `constant + sum(linear[i]*x_i) + sum(quadratic[i,j]*x_i*x_j)` for `i < j`.
- `qubo_to_ising(qubo)` substitutes `x_i=(1-Z_i)/2`. Its `operator` excludes the
  separately returned `offset`; add that offset to every energy/expectation.
- `build_qaoa_circuit(cost, gamma, beta, measure=False)` applies H, the cost
  phase, and `RX(2*beta)`. Measured circuits use one full-width classical register.
- `decode_counts(raw_counts, measured_circuit)` verifies final identity wiring
  and layout, then reverses plain displayed Qiskit strings once. Pass neither
  already-canonical bits nor integer/hex/multiple-register representations.
  `decode_state_index(index, num_actions)` handles state indices separately.
- `optimize_qaoa(cost, ...)` optimizes the exact full-distribution expectation,
  including penalties, using seeded COBYLA starts. Only converged starts can
  supply angles; failed starts stay in its report. All starts failing raises an
  error. It measures the final circuit on BasicSimulator, with measurement/layout
  checks before and after transpilation, and retains all raw counts.
- `summarize_samples(scenario, canonical_counts, alpha, optimal_bits=...)` calls
  the real `scoring.evaluate_plan`. The caller supplies the complete classical
  optimum set established by the authoritative classical reference. This function
  does not solve a classical problem. Both sample rates divide by all shots.

The builder reads normalizations, penalty, and default alpha from the scenario.
It checks finite inputs, all-action normalization bounds, and exactly two
candidate actions per encounter. Availability never removes a coverage candidate.
General coverage quadratization and multi-layer QAOA are outside this milestone.

## Executed verification

On the task branch without `scoring.py`: **55 passed, 13 skipped**. The skips
explicitly identify missing scorer integration; they are not passing integration.

Against the actual authoritative scorer source at unmerged commit
`871f904c4e9effe02553bafd5c2bc29b4c8a02bf` on `sanjhay/scoring`:
**68 passed, no skips**. The following command loads the scorer's Git object
in memory without copying its source into the branch, then runs the same tests:

```sh
.venv/bin/python - <<'PY'
import subprocess, sys, types, pytest
ref = '871f904c4e9effe02553bafd5c2bc29b4c8a02bf'
source = subprocess.check_output(['git', 'show', f'{ref}:scoring.py'], text=True)
scoring = types.ModuleType('scoring')
scoring.__file__ = f'git:{ref}:scoring.py'
exec(compile(source, scoring.__file__, 'exec'), scoring.__dict__)
sys.modules['scoring'] = scoring
raise SystemExit(pytest.main(['tests/test_quantum.py', '-q']))
PY
```

The scorer subsequently merged into main at
`c3cce0d8185d212b0dc79e54f9be5128d050f6ec`. The task branch was updated from
that main commit, and the full suite was run normally, including the
scorer tests. **88 passed, no skips**. No temporary scorer loader is needed now.

The classical solver subsequently merged at
`f7d18c51a6fb1d563c94b5584148cde5f6e9a3c7`. The unchanged integrated suite
collected and passed **113 tests**, including `tests/test_classical.py`, with no
failures or skips. Additional quantum integration tests compare complete tied
optimal sets across all four alphas and three availability settings and recheck
the saved run records against the classical implementation. With these 14 new
checks the complete suite collected **127 tests: 127 passed, 0 failed, 0 skipped**.

Fetch the named scorer commit read-only if that Git object is not already local.
The tests check all 64 plans at alpha 0, .25, .5, 1 for original, B2 unavailable,
and A1+B1 unavailable: **768 three-way comparisons** of scorer, QUBO, and basis
energy plus offset. They also check 24 original valid plans, all stated optimum
references with numerical tolerance, infeasibility, six single-action and several
multi-action measured patterns, nonidentity layout rejection, nonzero-angle
evolution against direct matrix evolution, and reproducible seeded optimization.

Also executed: JSON parsing/validation of the original data, `pip check` (no broken
requirements), and `git diff --check`. The original file was not modified. Its
computed reserve upper bound is `0.8254826675849403`, below `0.8254830119`.

## Initial measured run

`results/initial-p1-original-seed7-20261114/run-classical.json` preserves source/data hashes,
scorer provenance, all optimizer attempts, angles, seeds, settings, raw Qiskit
counts, canonical counts, and metrics using the merged scorer and the complete
optimal set from `classical.enumerate_plans` and `classical.solve_exact`. The earlier
`run.json` and `run-merged.json` preserve their original verification provenance.
The reproduction script is a single saved run artifact, not `experiments.py`.

After the real-scorer tests pass, reproduce without overwriting the saved run:

```sh
.venv/bin/python results/initial-p1-original-seed7-20261114/reproduce.py \
  --output /tmp/qubital-reproduced-run.json
```

The original scenario at alpha .25, seed 7, four starts, and 4096 shots produced:

| Quantity | Measured result |
| --- | --- |
| gamma | 0.5255145508363027 |
| beta | 2.6753177487745288 |
| Exact penalized expectation at those angles | 0.8142468191952472 |
| Mean penalized sampled objective | 0.82163172881916 |
| Valid under modeled rules | 3830/4096 = 93.505859375% |
| Classical-optimal samples | 146/4096 = 3.564453125% |
| Classical reference objective (`100011`) | 0.42898718432622596 |

These are initial one-layer simulator results from one seed, not a guarantee of
global angle optimality or a claim of quantum advantage. Invalid samples retain
their penalties and remain in both denominators.

## Shared validation follow-up and next integration

Scorer and classical integration are verified against the merged foundation.
The complete classical optimal sets equal every QUBO minimum when a feasible plan
exists (absolute comparison tolerance `1e-12`, no relative tolerance):

| Availability | alpha 0 | alpha .25 | alpha .5 | alpha 1 |
| --- | --- | --- | --- | --- |
| Original | `000111` | `100011` | `110001` | `110001` |
| B2 unavailable | `110001` | `110001` | `110001` | `110001` |
| A1 and B1 unavailable | no valid plan | no valid plan | no valid plan | no valid plan |

Every listed optimum is the complete singleton set. In infeasible cases,
`classical.solve_exact` returns `None` and all penalized QUBO minima remain invalid.
The saved distribution's metrics were rechecked using the classical reference;
valid/optimal counts remain 3830/146 out of 4096. A rerun with that reference
reproduces angles, all optimizer attempts, all raw/canonical counts and metrics
exactly. Historical JSON records retain their original metadata. Scorer/classical
integration has no remaining blocker; broader experiments remain a separate task.

No scoring API or mathematical-model change is requested. The inspected scorer's
loader does not yet enforce every handoff requirement. Proposed scorer
rejection tests: missing/wrong schema version; duplicate satellites, companies,
encounters or coverage; nonfinite/nonpositive numeric inputs; fuel above reserve;
fuel normalization below the all-action sum; and encounter candidate counts other
than two. These gaps do not affect the validated original data. The quantum
builder checks the numeric and coverage assumptions needed by its encoding,
without replacing the authoritative loader or scorer.
