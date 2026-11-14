"""Local hardware-layout tests; no credentials or IBM services are used."""

import pytest
from qiskit import QuantumCircuit, transpile
from qiskit.providers.fake_provider import GenericBackendV2

from research.hardware_plan import verify_layout


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
