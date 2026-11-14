# Qubital hardware proposal — not submitted

The read-only IBM checks succeeded with personal environment variables
`qiskithacks` and `ibmcrn`. Their presence and the active-instance match were
checked without displaying or saving either value. No account was saved, and
no IBM job or server dry-run was submitted.

## Proposed workload

| Circuit | Shots |
| --- | ---: |
| Saved optimized six-qubit, one-layer QAOA at alpha .25 | 1024 |
| Single-action mapping controls A1, A2, A3, B1, B2, B3 | 32 each |
| Total | 1216 across seven circuits |

Use the saved angles gamma `0.5255145508363027`, beta `2.6753177487745288`.
No on-hardware parameter optimization, mitigation, twirling, or dynamical
decoupling is proposed. This is a first hardware comparison of the saved circuit.

The proposed backend is **ibm_fez**, operational with zero pending jobs at the
snapshot. Accessible operational processors were ibm_fez (156 qubits, 0 pending),
ibm_marrakesh (156, 0 pending), and ibm_kingston (156, 237 pending). Queue and
calibration snapshots can change before any later authorized submission.

`verified-ibm-fez/` contains the logical circuits, actual locally transpiled ISA
circuits, and the safe live report. Logical action order A1,A2,A3,B1,B2,B3 maps
to physical qubits **122,143,123,121,136,124**, then classical bits 0 through 5.
All six controls use the same final physical qubits as QAOA. The QAOA ISA circuit
has depth 100, with 35 CZ, 78 RZ, 71 SX, and six measurements. The preflight
checks the full logical/physical/classical mapping; the independent core decoder
continues to require its original identity layout.

## Allocation and usage estimate

IBM reported 0 RUs consumed, a 10-RU usage limit, and 600 seconds remaining at the
check, matching the user-reported 10 RUs. The API did not return a separate RU
allocation field, so the report labels its derived balance as remaining to the
usage limit. Reports include timestamps and usage periods; check again before
any future submission.

For standard QPU workloads, IBM defines one RU as one minute of QPU compute time.
The backend-duration model, using its 250-microsecond default repetition delay
and a two-second one-subjob overhead assumption, estimates **2.309 seconds /
0.0385 RU**. IBM's simpler 350-microsecond-per-execution heuristic gives
**2.426 seconds / 0.0404 RU** for one subjob, or **14.426 seconds / 0.2404 RU**
for seven subjobs. These are planning scenarios, not guaranteed bounds or a
server billing quote; actual splitting, calibration, and overhead can differ.

Sources: [IBM usage estimation](https://quantum.cloud.ibm.com/docs/en/ibm-quantum-compute/estimate-job-run-time)
and [plan/RU definitions](https://quantum.cloud.ibm.com/docs/en/ibm-quantum-platform/plans-overview).

## Repeat read-only preparation

The existing quantum environment and dependency pins are unchanged. A separate
environment was used for Runtime 0.46.1, which supports Qiskit 2.2.3. The optional
dependency closure is pinned in `requirements-ibm-preflight.txt`.

```sh
python3 -m venv /tmp/qubital-ibm-venv
/tmp/qubital-ibm-venv/bin/python -m pip install -r requirements-ibm-preflight.txt
/tmp/qubital-ibm-venv/bin/python results/hardware-proposal-20261114/prepare.py \
  --check-ibm --output-dir /tmp/qubital-new-ibm-proposal
```

Set the personal variables through environment settings; never put their values
in source, shell command arguments, Git, or chat. `--api-key-env quiskithacks`
supports the spelling from the original request if that name is intentionally
bound instead; the verified current binding is `qiskithacks`.

The script has no submission path. Read-only service initialization, allocation
and processor metadata, and local transpilation are its only IBM operations.
Without `--check-ibm`, preparation is entirely offline. `prepared/` preserves the
earlier offline proposal and its then-unavailable credentials status; it is not
the live verification report. Further hardware execution requires a new explicit
authorization after reviewing this proposal.
