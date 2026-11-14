# Qubital collaboration contract

- SanjhayK owns scenario data, `scoring.py`, `classical.py`, and their tests.
  Kartikeya Pendem owns `quantum.py`, `tests/test_quantum.py`, and quantum results.
  Dashboard and experiment orchestration are later tasks.
- The user integrates shared configuration and reviews PRs. Keep dependency changes
  small and explain them. Do not merge, overwrite, or cherry-pick teammate work.
- Use a task branch from inspected current main; preserve existing changes. Commit
  reviewable work, open a PR when authorized, and do not merge it.
- Consume `load_scenario(path)` and `evaluate_plan(scenario, canonical_bits, alpha)`
  from the authoritative scorer. Its stable objective field is `objective_score`;
  feasibility is `valid`. Do not introduce another scorer or classical solver.
- Canonical bits follow scenario `action_order`; action i maps to qubit i. Reverse
  only standard displayed single-register Qiskit count strings after verifying
  measurement wiring. State indices and canonical bits have separate handling.
- Company burden is sum(fuel / remaining_reserve); L is sum of squared burdens.
  Objective is `(1-alpha)*F/fuel_normalization + alpha*L/reserve_normalization
  + violation_penalty*(uncovered_encounters + unavailable_selected)`.
  Read constants from data; use finite alpha in [0,1] and full precision.
- Each core encounter has exactly two candidates, including unavailable actions.
  Availability adds its own penalty. Preserve normalization on availability edits.
  Validate computed bounds <= declared bounds; exact equality is unnecessary.
- Verify all 64 original plans at alpha 0, .25, .5, 1: scorer = QUBO = operator
  basis energy + offset. Test every single-action measurement and nonzero-angle
  QAOA evolution. Report absent-scorer skips separately from passing integration.
- Optimize with invalid-sample penalties intact. Save seeds, settings, angles,
  raw counts, and rates over all shots. Use only authoritative classical reference
  optima; never substitute classical plans for failed quantum samples.
- Values are synthetic. Validity means valid under modeled rules; do not claim
  physical safety, satellite lifetime prediction, or quantum speedup.
