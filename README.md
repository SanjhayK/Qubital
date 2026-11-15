# Qubital

Qubital compares classical methods and one-layer QAOA for simplified satellite
response-burden allocation. It is a verified small optimization study, not an
orbital maneuver planner. It includes ideal local simulations and an actual
fixed-angle IBM hardware comparison. No quantum advantage is claimed.

## Two separate models

| Model | Decision | Score and input |
| --- | --- | --- |
| Synthetic action selection | Choose predefined actions covering four encounters | Invented fuel/reserve values in `data/original.json`; `scoring.py`, `classical.py`, `quantum.py` |
| Frozen-data responsibility | Assign each of six encounters to OneWeb or Starlink | Modeled fleet/satellite workload on real SOCRATES screening predictions; `research/` |

Bit meanings differ: synthetic `000000` selects no actions and is invalid;
responsibility `000000` assigns every event to Starlink. Neither model proves
physical maneuver safety. Priority weights are workload assumptions, not measured
fuel or true collision probabilities.

## Install and verify

Use Python 3.12 and the pinned dependencies. No IBM credentials are needed.

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-research.txt
QUBITAL_SOCRATES_DIR=/path/to/socrates_snapshot python -m pytest -ra
```

The private frozen SOCRATES package must be obtained separately and extracted;
point the variable at its `socrates_snapshot` directory. Without it, relevant
integration tests report skips. A passing partial suite is not full data
verification. Do not commit the package or credentials. Optional IBM preflight
dependencies are separate in `requirements-ibm-preflight.txt`.

## Results and reproduction

- [Current optimizer checks](research/ROBUSTNESS.md): four cases, seeds 7/19/43,
  four starts/seed, 4096 final shots. BFGS converged on 48/48 starts; the preceding
  larger-budget COBYLA study converged on 20/48. Both remain separate from v2.
- [Comparison figure](results/responsibility-p1-robustness-comparison-20261115/comparison.png)
  and [seed-level table](results/responsibility-p1-robustness-comparison-20261115/comparison.csv).
- [Model and data provenance](research/README.md), [retained v2 findings](research/RESULTS.md),
  and [assumptions and limitations](research/VALIDATION.md).
- [Synthetic model and reproduction](QUANTUM.md).
- [Result directory guide](results/README.md), including failed runs and archived
  source, counts and optimizer traces. Large traces are losslessly gzip-compressed;
  the verifiers read them directly and check original-byte hashes.

Exact enumeration already solves all 64 assignments. QAOA's optimum-hit rates
exceed uniform sampling here; the recorded annealing baseline has higher hit
rates with a different computation budget. This is not a speedup benchmark.

## IBM hardware result

The priority/background-on BFGS circuit ran on **ibm_fez**, job
`dbsgu4habdes73fr5530`, on November 15, 2026 UTC. One SamplerV2 job executed 4096
main shots plus six 32-shot mapping controls (4288 total), without mitigation,
twirling or hardware training. The compiled main circuit has depth 142 and 54 CZ
gates. IBM reports 3 QPU seconds and .047299 RU consumed.

The device sampled the exact modeled optimum 208/4096 times (5.08%); its sampled
mean objective was .510667192. A higher optimum-hit percentage alone does not
imply better optimization: its mean objective was worse than the paired ideal
run. Gate/readout error, decoherence, drift and shot fluctuations are not isolated
by this single comparison. This remains conditional workload assignment, not
physical collision-avoidance validation.

[Raw counts, layout, job receipt, usage and paired analysis](results/responsibility-hardware-20261115/)
are preserved separately from the ideal results. `research.hardware_run check`
is offline; `submit` is the only spending path and requires an exact proposal
hash and a new output directory; `collect` retrieves the existing job without
resubmission. Do not rerun `submit` to retrieve a result. Earlier proposals remain
historical evidence.

SOCRATES/SATCAT input credit: **CelesTrak / T. S. Kelso**. See
[source definitions and reuse caveats](research/README.md#sources-and-access).
Raw data are not redistributed; no redistribution license is inferred.
