"""Research metric checks use deliberately tiny synthetic score dictionaries."""

import pytest

from research.experiments import annealing_menu, sample_metrics, train_and_sample_budgeted


def test_sample_metrics_never_substitute_an_unsampled_optimum():
    metrics = sample_metrics({"01": 3, "10": 1},
                             {"00": 0.0, "01": 1.0, "10": 2.0, "11": 3.0},
                             0.0, ["00"])
    assert metrics["best_actual_sampled_bits"] == ["01"]
    assert metrics["complete_optimum_hit_probability"] == 0
    assert metrics["full_score_sample_mean"] == 1.25
    assert metrics["absolute_regret"] == 1.25
    assert metrics["relative_gap"] is None


def test_flat_objective_avoids_misleading_relative_gap():
    metrics = sample_metrics({"0": 2, "1": 2}, {"0": 2.0, "1": 2.0}, 2.0, ["0", "1"])
    assert metrics["relative_gap"] is None
    assert metrics["absolute_regret"] == 0
    assert metrics["distinct_optimal_assignments"] == 2
    with pytest.raises(ValueError):
        sample_metrics({}, {"0": 2.0}, 2.0, ["0"])


def test_independent_annealing_menu_reports_its_full_query_budget():
    scores = {"00": 0.0, "01": 1.0, "10": 2.0, "11": 3.0}
    counts, queries = annealing_menu(scores, 2, 7)
    assert sum(counts.values()) == 4096
    assert queries == 4096 * 33
    assert counts == annealing_menu(scores, 2, 7)[0]


def test_budgeted_training_samples_actual_quantum_angles_and_reports_stop_status():
    import numpy as np
    from qiskit.quantum_info import Statevector
    from quantum import Qubo, build_qaoa_circuit, qubo_to_ising

    cost = qubo_to_ising(Qubo(("test_event_0", "test_event_1"), 0.0, (0.1, 0.2), {(0, 1): 0.2}))
    trained = train_and_sample_budgeted(cost, 7)
    assert trained["optimizer_evaluations"] == len(trained["history"]) <= 200
    assert sum(trained["raw_counts"].values()) == sum(trained["canonical_counts"].values()) == 4096
    state = Statevector.from_instruction(build_qaoa_circuit(cost, **trained["angles"]))
    # Independent literal energies in Qiskit's little-endian basis-index order.
    expected = float(np.dot(state.probabilities(), [0.0, 0.1, 0.2, 0.5]))
    assert trained["expectation"] == pytest.approx(expected, abs=1e-12)
    assert trained["expectation"] == min(row["expectation"] for row in trained["history"])
    assert trained["classical_substitution"] is False
    assert trained["sampling_succeeded"] is True
    assert (trained["training_status"] == "converged") == trained["optimizer_converged"]
