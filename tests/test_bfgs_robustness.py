"""Analytic derivative and saved all-case BFGS checks, without IBM access."""

import itertools
import json
import os
from pathlib import Path

import numpy as np
import pytest
from qiskit import qpy
from qiskit.quantum_info import Statevector

from quantum import Qubo, build_qaoa_circuit, qubo_to_ising
from research.robustness import ROOT, starts_for_seed
from research.robustness_bfgs import DifferentiableP1, SETTINGS, train_start


@pytest.mark.parametrize("width", [1, 2, 6])
def test_analytic_gradient_matches_independent_central_differences(width):
    rng = np.random.default_rng(43)
    cost = qubo_to_ising(Qubo(tuple(str(i) for i in range(width)), 2.3,
                              tuple(rng.normal(size=width)),
                              {pair: float(rng.normal()) for pair in itertools.combinations(range(width), 2)}))
    engine = DifferentiableP1(cost)
    for angles in (np.array([0., 0.]), np.array([-1.3, .7]), np.array([12.1, -4.2])):
        value, gradient = engine.value_gradient(angles)
        finite = [(engine.expectation(angles + np.eye(2)[i] * 1e-6) - engine.expectation(angles - np.eye(2)[i] * 1e-6)) / 2e-6 for i in range(2)]
        np.testing.assert_allclose(gradient, finite, rtol=0, atol=1e-8)
        assert value == pytest.approx(engine.expectation(angles), abs=1e-12)


def test_bfgs_convergence_requires_a_small_actual_gradient():
    cost = qubo_to_ising(Qubo(("a", "b"), .4, (.1, .2), {(0, 1): .2}))
    attempt = train_start(cost, starts_for_seed(7, 1)[0], SETTINGS)
    assert attempt["optimizer_converged"]
    assert attempt["returned_gradient_infinity_norm"] <= 1e-6
    assert attempt["evaluations"] == attempt["gradient_evaluations"] == attempt["reported_nfev"] <= 2000
    assert attempt["qiskit_check_max_error"] < 1e-12


def test_saved_bfgs_study_and_recommendation():
    from research.experiments import verify_encoding
    from research.robustness_bfgs import verify
    from research.socrates_gate import adapt_case

    snapshot = Path(os.environ.get("QUBITAL_SOCRATES_DIR", "/workspace/attachments/qubital-socrates-frozen/socrates_snapshot"))
    output = ROOT / "results/responsibility-p1-robustness-bfgs-20261115"
    if not (snapshot / "SOCRATES-sort-minRange.csv").is_file():
        pytest.skip("private frozen data required for BFGS record integration")
    if not (output / "completed.json").is_file():
        pytest.skip("BFGS follow-up not yet executed")
    report = verify(snapshot, output)
    assert report["attempts_verified"] == 48
    assert report["actual_new_qaoa_final_shots"] == 49152
    recommendation = json.loads((output / "hardware-angle-recommendation.json").read_text())
    assert not recommendation["submission_authorized"]
    if recommendation["gate_passed"]:
        assert report["formally_converged_selected_runs"] == 12
        _, cost, _, _ = verify_encoding(adapt_case(snapshot, "priority"), .5, True)
        with (output / "recommended-logical.qpy").open("rb") as stream:
            circuits = qpy.load(stream)
        assert len(circuits) == 7 and all(c.num_qubits == 6 for c in circuits)
        angles = recommendation["angles"]
        actual = Statevector.from_instruction(circuits[0].remove_final_measurements(inplace=False))
        expected = Statevector.from_instruction(build_qaoa_circuit(cost, **angles))
        assert actual.equiv(expected)
        assert np.linalg.norm(DifferentiableP1(cost).value_gradient([angles["gamma"], angles["beta"]])[1], ord=np.inf) <= 1e-6
