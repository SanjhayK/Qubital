# Result directory guide

Current research uses `qubital.responsibility.v1`. Ideal simulations, historical
preparations and the actual IBM run are stored separately.

| Directory | Purpose |
| --- | --- |
| `responsibility-hardware-20261115/` | Actual ibm_fez job `dbsgu4habdes73fr5530`: seven circuits, 4288 shots, original/ISA QPY, raw counts, mapping controls, matched ideal comparison and allocation records |
| `responsibility-p1-robustness-comparison-20261115/` | Current cross-study figure, seed table and executed-check audit |
| `responsibility-p1-robustness-bfgs-20261115/` | All-case converged optimizer cross-check, original protocol/attempts/counts and current logical hardware-angle recommendation |
| `responsibility-p1-robustness-20261115/` | Larger-budget COBYLA follow-up, including nonconverged attempts; raw traces are `.json.gz` |
| `responsibility-p1-20261114-v2/` | Preserved original fixed-budget study, exact references and classical baselines |
| `responsibility-p1-20261114-v1/` | Preserved failed strict-convergence pilot; no final quantum samples |
| `research-gate-20261114/` | Frozen source hashes, selection and data-validation evidence |
| `initial-p1-original-seed7-20261114/` | Separate original synthetic-model results and reproduction script |
| `responsibility-hardware-proposal-20261114-matched/` | Historical v2 4096-main-shot device compilation; superseded angles |
| `responsibility-hardware-proposal-20261114/` | Earlier 1024-main-shot preparation; historical only |
| `hardware-proposal-20261114/` | Original synthetic-model IBM preflight and prepared circuits |

`compressed-traces.json` records the logical paths, original-byte SHA-256 hashes,
gzip hashes and byte sizes of all 48 compressed COBYLA traces. Decompression
reproduces the exact original bytes. It does not alter settings, attempts or
results, and Python verification works without manually extracting files.

Frozen source archives explain what produced historical runs. Completed runs
verify those archives and their scientific evidence; live documentation and
maintenance code may evolve. Unfinished plans still require matching live source.
Compression reduces the checked-out files, not earlier Git history.

No raw SOCRATES package is included. Full data verification requires the private
snapshot named by `QUBITAL_SOCRATES_DIR`; a skipped data test is not a pass.
