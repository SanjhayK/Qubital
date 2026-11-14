# Analysis validation and bounded critical review

**Assessment: share with the caveats below.** Internal arithmetic and recorded
ideal sampling are verified; operational validity, broad representativeness,
judge access, submission status, and raw-data redistribution rights are not.

| Statement | Evidence category | Check and limitation |
| --- | --- | --- |
| Frozen data describe real catalog objects | Published screening predictions | Hash, bytes, all rows/fields, UTC cutoffs, and derived slices checked; no observed collision or completed burn is measured |
| Six events are the primary case | Predeclared selection/model assumption | Earliest eligible six before solver output; six-hour lead rule is modeled, not an official standard |
| Two background records are aligned | Calculated filter plus catalog confirmation | Same cutoff/end time and name-candidate rule on both fleets; both are confirmed DEB; absence of other name matches is not exhaustive classification |
| UK identifies the operator company | Rejected interpretation | SATCAT join returns UK; group assignment uses documented constellation names/IDs instead |
| Both sides can respond | Explicit conditional assumption | Active catalog status does not establish maneuver capability; fixed/no-response cases tested |
| Priority weights measure fuel or actual event loss | Rejected interpretation | MAX_PROB ratio is modeled workload priority only; no scalar delta-v shortcut implemented |
| New model is mathematically encoded correctly | Executed verification | Independent direct scorer/QUBO/Ising+offset comparisons over all 256 real case assignments, plus synthetic/fixed/background tests |
| QAOA training converged | False for these runs | All 12 starts hit their 200-evaluation limit; actual fixed-budget angle histories and simulator counts retained |
| QAOA sampled more optima than uniform | Supported for this recorded benchmark | Three seeds, complete tied optimum sets, 4096 final samples/seed; no confidence/causal or general advantage claim |
| QAOA is better than classical optimization | Unsupported | Chain-best annealing has higher hit rates at a much larger cached-query budget; exact enumeration solves all 64 cases |
| Quantum offers a uniquely diverse menu | Unsupported here | Both uniform and QAOA recovered the full declared near-optimal menu in every seed |
| 100% validity proves safety | Rejected interpretation | Every free assignment is structurally allowed; coupled dynamics and real burns are absent |
| Hardware comparison completed | False | New-model circuits were locally recompiled; no job, server dry-run, or 156-wire statevector simulation was performed |

## Disconfirming checks and decisions

**Strongest counterargument:** this is a small weighted partitioning problem,
and the sampled subset repeats one OneWeb satellite against six Starlink objects.
The burden criterion and assumed response capability are simplified policy choices.
Exact enumeration already produces the full optimum set. Shallow quantum sampling
is not needed operationally to solve this instance.

**A check that can disprove a benefit:** compare complete optimum hits, full-score
regret, and the predeclared near-menu coverage against matched-returned-sample
uniform and independent-chain classical outputs. This check was executed; it
does not support superiority over the classical baseline or unique menu diversity.

**Recommendation:** keep the original synthetic reference, the new verified
responsibility model, and these negative/limited findings. Defer physical maneuver
claims, larger instances, p2, noise/mitigation, and hardware execution. Protect the
five-minute story, verification, access checks, and two human rehearsals.

## Different uncertainties are not interchangeable

- Shot uncertainty: 4096 final ideal samples per case/seed. Seed-range whiskers
  are not confidence intervals for those shot estimates.
- Optimizer uncertainty: three initialization seeds, finite budget, no formal
  convergence; every seed is retained, including the earlier failed pilot.
- Data uncertainty: forecasts, source-data age, later/partly undated SATCAT
  validation, and incomplete counterpart classification. DSE is not covariance.
- Model uncertainty: response capability, responsibility-as-workload, and event
  independence; the close pair may require coupled dynamics. More shots cannot
  validate these physical assumptions.

## Context and guidance actually available

Read: AGENTS.md, QUANTUM.md, original code/tests/results, old Orbit Accord
handoff, the new frozen ZIP manifests/scripts/research review/teammate handoff,
and the current conversation. The original 13-page teammate PDF is not included
in this ZIP; no claim is made to have independently read it. The user-selected
Qubital name, two-person staffing, five-minute format, no asteroid pivot, and no
new IBM job authorization override older proposals.

Discovered/read cloud skills: validate-data, scientific-problem-selection,
jupyter-notebook, grill-me and its grilling dependency. Their longer interview
and academic timelines were bounded by the user's instructions. The critical
review above used counterarguments and disproof tests, not an endless interview.
Cloud notebook helper/template resources could not be read and local notebook
kernel packages were absent, so the accepted reproducible-script deliverable was
used instead; no notebook execution is claimed.

No additional skills were downloaded or installed in this task. NVIDIA's reviewer
was not in the available skill catalog, and the external SKILL_REVIEW.json is
another session's evidence, not a scan performed here. Consequently no fresh
SkillSpector score, provider-key use, external model upload, or tracing is claimed.
No marketplace, Runtime migration, Estimator mitigation, Scite, or frontend setup
was introduced. Scientific calculations and explicit verification remain the
evidence, not the presence or score of a skill.

Primary source checks used CelesTrak SOCRATES/SATCAT format/status/use-policy
pages without redownloading the raw data. An inaccessible guessed source page
was not repeatedly retried. The Devpost rules link was attempted read-only via
web lookup and a bounded public request, but was unavailable; no submission,
website edit, account login, or repository-visibility change occurred.
