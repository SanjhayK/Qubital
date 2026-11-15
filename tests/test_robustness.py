"""Robustness protocol: equivalent circuits, honest selection and preserved data."""

from copy import deepcopy
import itertools
import json
import os
from pathlib import Path

import numpy as np
import pytest
from qiskit import qpy
from qiskit.quantum_info import SparsePauliOp, Statevector

from quantum import IsingCost, Qubo, build_qaoa_circuit, qubo_to_ising
from research.robustness import (P1State, SETTINGS, sample_selected, select_attempt,
                                 starts_for_seed, train_start)


@pytest.mark.parametrize("width", [1, 2, 6])
def test_fast_p1_probabilities_and_full_expectation_equal_qiskit(width):
    rng = np.random.default_rng(19)
    cost = qubo_to_ising(Qubo(tuple(str(i) for i in range(width)), 2.3,
                              tuple(rng.normal(size=width)),
                              {pair: float(rng.normal()) for pair in itertools.combinations(range(width), 2)}))
    engine = P1State(cost)
    for angles in ([0, 0], [-3.25, .98], [21.7, -6.1], [7.3, 0]):
        state = Statevector.from_instruction(build_qaoa_circuit(cost, *angles))
        np.testing.assert_allclose(engine.probabilities(angles), state.probabilities(), rtol=0, atol=1e-12)
        assert engine.expectation(angles) == pytest.approx(float(state.expectation_value(cost.operator).real + cost.offset), abs=1e-12)
        assert sum(engine.probabilities(angles)) == pytest.approx(1)


def test_training_engine_rejects_nondiagonal_cost_and_device_width():
    with pytest.raises(ValueError, match="diagonal"):
        P1State(IsingCost(SparsePauliOp.from_list([("X", 1)]), 0, ("e",)))
    with pytest.raises(ValueError, match="small logical"):
        P1State(IsingCost(None, 0, tuple(str(i) for i in range(156))))


def test_start_schedule_is_reproducible_distinct_and_matches_v2_first_start():
    for seed in SETTINGS["training_seeds"]:
        initial = starts_for_seed(seed, 4)
        assert initial == starts_for_seed(seed, 4)
        assert initial[0] == np.random.default_rng(seed).uniform([0, 0], [2 * np.pi, np.pi]).tolist()
        assert len(set(map(tuple, initial))) == 4
    assert starts_for_seed(7, 4) != starts_for_seed(19, 4)


def test_selection_respects_convergence_and_keeps_nonconverged_results_honest():
    attempts = [{"start_index": 0, "best_expectation": .1, "optimizer_converged": False},
                {"start_index": 1, "best_expectation": .2, "optimizer_converged": True},
                {"start_index": 2, "best_expectation": .2, "optimizer_converged": True}]
    assert select_attempt(attempts)["start_index"] == 1
    nonconverged = deepcopy(attempts)
    for attempt in nonconverged:
        attempt["optimizer_converged"] = False
    assert select_attempt(nonconverged)["start_index"] == 0
    assert not select_attempt(nonconverged)["optimizer_converged"]
    with pytest.raises(ValueError, match="no training"):
        select_attempt([])


def test_optimizer_tracks_budget_and_samples_selected_circuit_reproducibly():
    cost = qubo_to_ising(Qubo(("a", "b"), .4, (.1, .2), {(0, 1): .2}))
    settings = SETTINGS | {"max_evaluations_per_start": 20}
    attempt = train_start(cost, starts_for_seed(7, 1)[0], settings)
    assert attempt["evaluations"] == attempt["reported_nfev"] == len(attempt["history"]) <= 20
    assert attempt["best_expectation"] == min(h["expectation"] for h in attempt["history"])
    assert attempt["qiskit_check_max_error"] < 1e-12
    first = sample_selected(cost, attempt, 7, 128)
    assert first == sample_selected(cost, attempt, 7, 128)
    assert sum(first["counts"].values()) == sum(first["raw_counts"].values()) == 128
    assert first["angles"] == dict(zip(("gamma", "beta"), attempt["best_angles"]))


def test_complete_saved_study_and_recommended_logical_circuit():
    from research.experiments import verify_encoding
    from research.robustness import ROOT
    from research.socrates_gate import adapt_case
    from research.verify_robustness import verify

    snapshot = Path(os.environ.get("QUBITAL_SOCRATES_DIR", "/workspace/attachments/qubital-socrates-frozen/socrates_snapshot"))
    if not (snapshot / "SOCRATES-sort-minRange.csv").is_file():
        pytest.skip("private frozen data required for robustness record verification")
    output = ROOT / "results/responsibility-p1-robustness-20261115"
    if not (output / "completed.json").is_file():
        pytest.skip("robustness experiment not yet executed")
    report = verify(snapshot, output)
    assert report["attempts_verified"] == 48
    assert report["actual_new_qaoa_final_shots"] == 49152
    recommendation = json.loads((output / "hardware-angle-recommendation.json").read_text())
    assert not recommendation["submission_authorized"]
    if recommendation["gate_passed"]:
        assert report["formally_converged_selected_runs"] == 12
        assert all(c["mean_expectation_no_worse_than_v2"] for c in report["case_comparison"])
        _, cost, _, _ = verify_encoding(adapt_case(snapshot, "priority"), .5, True)
        with (output / "recommended-logical.qpy").open("rb") as stream:
            circuits = qpy.load(stream)
        assert len(circuits) == 7 and all(c.num_qubits == 6 for c in circuits)
        actual = Statevector.from_instruction(circuits[0].remove_final_measurements(inplace=False))
        expected = Statevector.from_instruction(build_qaoa_circuit(cost, **recommendation["angles"]))
        assert actual.equiv(expected)
