# Qubital — five-minute research handoff

Presenters: **Kartikeya Pendem and Sanjhay**. This is a draft talk/slide outline
for the two presenters, not a claim that a rehearsal or submission has occurred.
Use six slides and the final figure; do not depend on a live app or IBM execution.
Keep derivations and full optimum sets as backup material. Target about 550 words
plus figure pauses; rehearse twice with a five-minute hard stop.

## 1 · Question · 0:00–0:35 · Kartikeya

**Slide:** “Who should take conditional responsibility for each screening event?”

“Qubital studies how to distribute response responsibility between satellite
groups. Our original verified example used synthetic fuel and reserve values.
Today we add a separate research case built from real-object public screening
predictions. Our question is narrow: on six frozen events, how does shallow QAOA
sample low-burden assignments compared with exact and simple classical methods?
We are not calculating safe burns or claiming a quantum speedup.”

## 2 · Data and what is modeled · 0:35–1:15 · Sanjhay

**Slide:** source → 17 cross-fleet → 10 eligible → earliest six; two aligned debris loads.

“We froze CelesTrak SOCRATES data and verified its hash and 198,115 rows. From 17
OneWeb–Starlink events, our explicitly modeled six-hour lead rule leaves ten;
we selected the earliest six before running solvers. Two catalog-confirmed debris
records fit the same window. Two selected events share a satellite and are only
2.844 seconds apart. They are distinct, but physically coupled responses may be
possible. These are forecasts, not observed collisions; our weights and assumed
response options are modeling choices.”

## 3 · Formulation and verification · 1:15–2:10 · Kartikeya

**Slide:** one qubit per event; `1=OneWeb`, `0=Starlink`; fleet + satellite burden squares.

“One bit assigns each event's conditional responsibility. In this model, all
zeros means all Starlink. Burden is fixed background plus assigned event weight.
We minimize a half-fleet, half-satellite squared-burden objective, with a fixed
normalizer across debris on and off. We compare unit weights with a normalized
screening-priority variant. These are not fuel or true collision-loss units.
Squaring affine burdens gives a QUBO. For every assignment in all four cases,
our direct scorer, QUBO, and Qiskit basis-state energy plus offset agree. The
largest discrepancy is about three times ten to the minus sixteen.”

## 4 · Actual comparison · 2:10–3:35 · Kartikeya

**Slide:** `results/responsibility-p1-20261114-v2/final-report/comparison.png`.

“We ran one-layer ideal QAOA with three seeds, 200 expectation evaluations per
start, and 4,096 final shots per case and seed. An initial convergence-gated
pilot exhausted its budget without sampling. We retained it, then disclosed a
fixed-budget policy: sample the best quantum angles actually visited. All twelve
sampling runs completed, but none formally converged.

“For priority weights with debris, QAOA hit the exact optimum about 4.52 percent
of the time, versus 1.60 percent for uniform sampling. Independent annealing
chain-best outputs reached 36.78 percent, using much more classical query work.
The bars summarize three seeds; whiskers are seed ranges, not confidence
intervals. Returned-sample counts match, computational budgets do not. QAOA
improved over uniform in these runs, but this is no evidence of advantage over
classical optimization. Exact enumeration already supplies the full small menu.”

## 5 · Sensitivity and strongest objection · 3:35–4:30 · Sanjhay

**Slide:** unit optimum count 15 → 6; priority optimum `000010` → `000010`.

“Debris changes the complete unit-weight optimum set, but the priority optimum
stays the same. We do not force a positive debris story. Both QAOA and uniform
sampling recovered the full declared near-optimal menu, so diversity was not a
unique quantum benefit. A refusal can leave just one deterministic assignment;
we evaluate that directly, not with zero-qubit QAOA. The strongest objection is
that this tiny, selected partitioning model omits trajectory changes, feasibility,
capability uncertainty, and much of real workload. Catalog validation was also
retrieved later than the raw cutoff. It is a retrospective benchmark.”

## 6 · Takeaway · 4:30–5:00 · Kartikeya

**Slide:** verified model → reproducible comparison → limitations; hardware proposal only.

“Our contribution is a reproducible formulation and verified classical–quantum
comparison with explicit real-versus-modeled quantities. The original synthetic
study is preserved. We have a separately recompiled fixed-angle hardware
proposal, but no hardware result or new job submission. Next we would validate
response assumptions and coupling with domain evidence, then compare methods on
harder matched-budget instances. Thank you.”

## Backup: short answers

- **Why not just enumerate?** For six bits, enumerate: it is the strongest exact
  reference and already gives every option. This is an implementation/research
  demonstration, not a reason to replace classical optimization.
- **Is MAX_PROB the actual collision probability?** No. It is a conservative
  screening construction; using its ratio as workload priority is explicit policy.
- **Why not actual fuel?** The source lacks maneuver geometry, propulsion, and
  reserves. A scalar miss-distance/lead-time shortcut cannot supply them.
- **Is 100% validity a success?** It is structural assignment validity, not safety
  or improved performance over the original model's different feasible set.
- **What about the close pair?** It is preserved as distinct events; their shared
  satellite and 2.844-second separation are a coupling limitation.
- **What changed after the pilot?** Only the stopping/sampling policy. The first
  failures remain; all seeds, weights, model settings, and 200-call budget stayed.
- **Did this run on IBM?** No. Ideal simulator results and a read-only, recompiled
  hardware proposal are kept separate. No device noise result is claimed.

## Finish checklist for the presenters

- Rehearse once to cut jargon, once for the speaker handoff and hard time limit.
- Include the final figure and supporting notes in the presentation.
- Keep data attribution and all material limitations visible, not only in Q&A.
- Confirm judge access to the actual submitted artifacts. The repo is private;
  no visibility change or judge invitation was made.
- Read the actual organizer rules and retain any required disclosures. The
  supplied Devpost page was unreachable from this environment; no rule compliance
  or submission confirmation is asserted. No optional tool coauthor credits were added.
- Use the conservative user-supplied Eastern deadlines: Saturday 9 PM challenge,
  Sunday 8 AM main submission, 9:30–10:30 AM presentation session. Confirm newer
  organizer announcements directly; do not infer a deadline from a search snippet.
