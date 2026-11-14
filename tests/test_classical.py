import copy

import pytest

from classical import (
    enumerate_plans,
    pareto_frontier,
    solve_exact,
    solve_greedy,
    solve_simulated_annealing,
)
from scoring import load_scenario


@pytest.fixture
def scenario():
    return load_scenario("data/original.json")


def make_actions_unavailable(scenario, action_ids):
    changed = copy.deepcopy(scenario)

    for action in changed["actions"]:
        if action["id"] in action_ids:
            action["available"] = False

    return changed


def test_enumeration_returns_all_64_plans(scenario):
    plans = enumerate_plans(scenario, alpha=0.25)

    assert len(plans) == 64
    assert len({plan["canonical_bits"] for plan in plans}) == 64
    assert sum(plan["valid"] for plan in plans) == 24


@pytest.mark.parametrize(
    ("alpha", "expected_bits"),
    [
        (0.0, "000111"),
        (0.25, "100011"),
        (1.0, "110001"),
    ],
)
def test_exact_solver_finds_expected_optimum(
    scenario,
    alpha,
    expected_bits,
):
    result = solve_exact(scenario, alpha)

    assert result is not None
    assert result["valid"] is True
    assert result["canonical_bits"] == expected_bits


def test_exact_solver_uses_default_alpha(scenario):
    result = solve_exact(scenario)

    assert result is not None
    assert result["canonical_bits"] == "100011"


def test_exact_solver_returns_none_when_no_agreement_exists(scenario):
    impossible = make_actions_unavailable(
        scenario,
        {"A1", "B1"},
    )

    assert solve_exact(impossible, alpha=0.25) is None


@pytest.mark.parametrize("alpha", [0.0, 0.25, 1.0])
def test_greedy_solver_returns_valid_plan(scenario, alpha):
    result = solve_greedy(scenario, alpha)

    assert result["valid"] is True
    assert result["uncovered_encounters"] == []
    assert result["unavailable_selected"] == []


@pytest.mark.parametrize(
    ("alpha", "expected_bits"),
    [
        (0.0, "000111"),
        (0.25, "100011"),
        (1.0, "110001"),
    ],
)
def test_greedy_solver_matches_known_optimum(
    scenario,
    alpha,
    expected_bits,
):
    result = solve_greedy(scenario, alpha)

    assert result["canonical_bits"] == expected_bits


def test_greedy_reports_invalid_when_no_agreement_exists(scenario):
    impossible = make_actions_unavailable(
        scenario,
        {"A1", "B1"},
    )

    result = solve_greedy(impossible, alpha=0.25)

    assert result["valid"] is False


def test_simulated_annealing_returns_valid_plan(scenario):
    result = solve_simulated_annealing(
        scenario,
        alpha=0.25,
        seed=42,
    )

    assert result["valid"] is True


def test_simulated_annealing_finds_default_optimum(scenario):
    exact = solve_exact(scenario, alpha=0.25)
    annealed = solve_simulated_annealing(
        scenario,
        alpha=0.25,
        seed=42,
    )

    assert exact is not None
    assert annealed["canonical_bits"] == exact["canonical_bits"]
    assert annealed["objective_score"] == pytest.approx(
        exact["objective_score"]
    )


def test_simulated_annealing_is_reproducible(scenario):
    first = solve_simulated_annealing(
        scenario,
        alpha=0.25,
        seed=123,
    )
    second = solve_simulated_annealing(
        scenario,
        alpha=0.25,
        seed=123,
    )

    assert first == second


def test_simulated_annealing_reports_invalid_if_none_exists(scenario):
    impossible = make_actions_unavailable(
        scenario,
        {"A1", "B1"},
    )

    result = solve_simulated_annealing(
        impossible,
        alpha=0.25,
        seed=42,
    )

    assert result["valid"] is False


@pytest.mark.parametrize(
    ("parameter", "value"),
    [
        ("restarts", 0),
        ("steps_per_restart", 0),
        ("initial_temperature", 0),
        ("cooling_rate", 0),
        ("cooling_rate", 1.01),
    ],
)
def test_simulated_annealing_rejects_bad_parameters(
    scenario,
    parameter,
    value,
):
    arguments = {parameter: value}

    with pytest.raises(ValueError):
        solve_simulated_annealing(
            scenario,
            alpha=0.25,
            **arguments,
        )


def test_pareto_frontier_contains_key_tradeoff_plans(scenario):
    frontier = pareto_frontier(scenario)
    frontier_bits = {
        plan["canonical_bits"]
        for plan in frontier
    }

    assert "000111" in frontier_bits
    assert "100011" in frontier_bits
    assert "110001" in frontier_bits
    assert all(plan["valid"] for plan in frontier)


def test_no_frontier_plan_is_dominated(scenario):
    frontier = pareto_frontier(scenario)
    valid_plans = [
        plan
        for plan in enumerate_plans(scenario)
        if plan["valid"]
    ]

    for candidate in frontier:
        dominators = [
            other
            for other in valid_plans
            if other["canonical_bits"] != candidate["canonical_bits"]
            and other["fuel_total"] <= candidate["fuel_total"]
            and other["reserve_score"] <= candidate["reserve_score"]
            and (
                other["fuel_total"] < candidate["fuel_total"]
                or other["reserve_score"] < candidate["reserve_score"]
            )
        ]

        assert dominators == []


def test_classical_solvers_do_not_modify_scenario(scenario):
    original = copy.deepcopy(scenario)

    enumerate_plans(scenario, alpha=0.25)
    solve_exact(scenario, alpha=0.25)
    solve_greedy(scenario, alpha=0.25)
    solve_simulated_annealing(
        scenario,
        alpha=0.25,
        seed=42,
        restarts=2,
        steps_per_restart=20,
    )
    pareto_frontier(scenario)

    assert scenario == original