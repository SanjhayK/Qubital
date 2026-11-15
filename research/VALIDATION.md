# Assumptions and validation

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
| V2 QAOA training converged | False for v2 | All 12 starts hit their 200-evaluation limit; fixed-budget histories and simulator counts retained |
| Follow-up training converged | Supported with optimizer-specific limits | Larger-budget COBYLA 20/48 starts; separately declared analytic-gradient BFGS 48/48; no global-optimality certificate. See ROBUSTNESS.md |
| QAOA sampled more optima than uniform | Supported for this recorded benchmark | Three seeds, complete tied optimum sets, 4096 final samples/seed; no confidence/causal or general advantage claim |
| QAOA is better than classical optimization | Unsupported | Chain-best annealing has higher hit rates at a much larger cached-query budget; exact enumeration solves all 64 cases |
| Quantum offers a uniquely diverse menu | Unsupported here | Both uniform and QAOA recovered the full declared near-optimal menu in every seed |
| 100% validity proves safety | Rejected interpretation | Every free assignment is structurally allowed; coupled dynamics and real burns are absent |
| Hardware comparison completed | Supported for one fixed-angle case | ibm_fez job dbsgu4habdes73fr5530; 4096 main + 192 control shots; raw counts/usage retained; no hardware training or mitigation; no isolated noise-cause or safety claim |

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
- Optimizer uncertainty: three root seeds and finite budgets; v2 did not formally
  converge, whereas the BFGS follow-up converged locally. Every seed and failed
  pilot remains retained. Local convergence does not certify a global optimum.
- Data uncertainty: forecasts, source-data age, later/partly undated SATCAT
  validation, and incomplete counterpart classification. DSE is not covariance.
- Model uncertainty: response capability, responsibility-as-workload, and event
  independence; the close pair may require coupled dynamics. More shots cannot
  validate these physical assumptions.
