"""Combined-PR checks: synthetic actions and real-case responsibility stay separate."""

import json
import os
from pathlib import Path

import pytest
from qiskit import qpy
from qiskit.quantum_info import Statevector

from quantum import build_qaoa_circuit, build_qubo, qubo_to_ising
from research.hardware_plan import verify_layout
from research.responsibility import build_responsibility_qubo, evaluate_assignment
from research.socrates_gate import adapt_case
from scoring import evaluate_plan, load_scenario

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def real_case():
    snapshot = Path(os.environ.get("QUBITAL_SOCRATES_DIR",
                                  "/workspace/attachments/qubital-socrates-frozen/socrates_snapshot"))
    if not (snapshot / "SOCRATES-sort-minRange.csv").is_file():
        pytest.skip("private frozen dataset required for combined model checks")
    return adapt_case(snapshot, "priority")


def test_all_zero_bits_have_different_explicit_model_semantics(real_case):
    synthetic = evaluate_plan(load_scenario(ROOT / "data/original.json"), "000000", .25)
    responsibility = evaluate_assignment(real_case, "000000", eta=.5, background=True)
    assert synthetic["selected_actions"] == []
    assert synthetic["valid"] is False and synthetic["objective_score"] == 8.0
    assert responsibility["model_id"] == "qubital.responsibility.v1"
    assert responsibility["valid"] is True
    assert len(responsibility["assignments"]) == 6
    assert all(assignment["group"] == "Starlink" for assignment in responsibility["assignments"])


def test_each_hardware_artifact_matches_its_own_model_and_angles(real_case):
    original = ROOT / "results/hardware-proposal-20261114/verified-ibm-fez"
    research = ROOT / "results/responsibility-hardware-proposal-20261114-matched"
    old = json.loads((original / "proposal.json").read_text())
    new = json.loads((research / "proposal.json").read_text())
    assert old["alpha"] == .25
    assert new["model_id"] == real_case["model_id"]
    assert new["eta"] == .5 and new["background"] is True
    assert old["angles"] != new["angles"]
    with (original / "circuits.qpy").open("rb") as stream:
        old_logical = qpy.load(stream)[0]
    with (research / "logical.qpy").open("rb") as stream:
        new_logical = qpy.load(stream)[0]
    costs = [qubo_to_ising(build_qubo(load_scenario(ROOT / "data/original.json"), .25)),
             qubo_to_ising(build_responsibility_qubo(real_case, eta=.5, background=True))]
    for logical, cost, angles in zip((old_logical, new_logical), costs, (old["angles"], new["angles"])):
        assert logical.num_qubits == 6  # Never densely simulate backend-width ISA circuits.
        actual = Statevector.from_instruction(logical.remove_final_measurements(inplace=False))
        expected = Statevector.from_instruction(build_qaoa_circuit(cost, **angles))
        assert actual.equiv(expected)
    with (research / "isa.qpy").open("rb") as stream:
        isa = qpy.load(stream)
    physical = verify_layout(isa[0])
    assert all(verify_layout(control) == physical for control in isa[1:])
    assert sum(c["shots"] for c in new["circuits"]) == new["shots"] == 4288
