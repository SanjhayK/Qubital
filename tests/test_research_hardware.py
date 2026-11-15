"""Local hardware-layout tests; no credentials or IBM services are used."""

import pytest
from qiskit import QuantumCircuit, transpile
from qiskit.providers.fake_provider import GenericBackendV2

from research.hardware_plan import choose_training_record, verify_layout


def test_nonidentity_backend_width_mapping_keeps_canonical_classical_order():
    logical = QuantumCircuit(6, 6)
    logical.h(range(6))
    logical.cx(0, 1)
    logical.measure(range(6), range(6))
    backend = GenericBackendV2(8, basis_gates=["rz", "sx", "x", "cx"], seed=7)
    compiled = transpile(logical, backend, initial_layout=[7, 6, 5, 4, 3, 2], seed_transpiler=7)
    assert compiled.num_qubits == 8
    assert verify_layout(compiled) == [7, 6, 5, 4, 3, 2]
    bad = compiled.copy()
    bad.data = [i for i in bad.data if i.operation.name != "measure"]
    bad.measure([7, 6, 5, 4, 3, 2], [5, 4, 3, 2, 1, 0])
    with pytest.raises(ValueError):
        verify_layout(bad)


def test_hardware_wiring_rejects_a_gate_after_that_qubit_was_measured():
    circuit = QuantumCircuit(6, 6)
    circuit.measure(range(6), range(6))
    circuit.x(0)
    with pytest.raises(ValueError):
        verify_layout(circuit)


def test_current_hardware_target_uses_verified_bfgs_records():
    import os
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    snapshot = Path(os.environ.get("QUBITAL_SOCRATES_DIR", "/workspace/attachments/qubital-socrates-frozen/socrates_snapshot"))
    if not (snapshot / "SOCRATES-sort-minRange.csv").is_file():
        pytest.skip("private snapshot required for all-case hardware-angle verification")
    runs = root / "results/responsibility-p1-robustness-bfgs-20261115"
    selected = choose_training_record(runs, snapshot)
    assert selected["seed"] == 19
    assert selected["optimizer_converged"] is True
    assert selected["training_and_sampling"]["angles"] == selected["angles"]
    assert selected["study_id"] == "qubital.p1.optimizer-robustness.bfgs.v1"


def test_current_study_cannot_bypass_snapshot_verification(tmp_path):
    import json
    (tmp_path / "protocol.json").write_text(json.dumps({"study_id": "qubital.p1.optimizer-robustness.bfgs.v1"}))
    with pytest.raises(ValueError, match="snapshot"):
        choose_training_record(tmp_path)


def test_nonconverged_followup_is_not_a_hardware_training_source(tmp_path):
    import json
    (tmp_path / "protocol.json").write_text(json.dumps({"study_id": "qubital.p1.optimizer-robustness.v1"}))
    with pytest.raises(ValueError, match="eligible"):
        choose_training_record(tmp_path)
