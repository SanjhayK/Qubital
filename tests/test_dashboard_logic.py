import copy

import pytest

from dashboard_logic import (
    build_classical_dashboard_state,
    company_burden_rows,
    encounter_rows,
    frontier_rows,
    scenario_with_unavailable_actions,
    selected_action_rows,
    top_sample_rows,
)
from scoring import evaluate_plan, load_scenario


@pytest.fixture
def scenario():
    return load_scenario("data/original.json")


def test_availability_change_uses_copy(scenario):
    original = copy.deepcopy(scenario)

    changed = scenario_with_unavailable_actions(
        scenario,
        {"B2"},
    )

    availability = {
        action["id"]: action["available"]
        for action in changed["actions"]
    }

    assert availability["B2"] is False
    assert all(
        available
        for action_id, available in availability.items()
        if action_id != "B2"
    )
    assert scenario == original


def test_unknown_unavailable_action_is_rejected(scenario):
    with pytest.raises(ValueError):
        scenario_with_unavailable_actions(
            scenario,
            {"UNKNOWN"},
        )


def test_default_dashboard_state(scenario):
    state = build_classical_dashboard_state(
        scenario,
        alpha=0.25,
    )

    assert state["total_plan_count"] == 64
    assert state["valid_plan_count"] == 24
    assert state["feasible"] is True
    assert state["exact"]["canonical_bits"] == "100011"
    assert state["greedy"]["canonical_bits"] == "100011"
    assert state["simulated_annealing"]["valid"] is True
    assert state["unavailable_actions"] == []


@pytest.mark.parametrize(
    ("alpha", "expected_bits"),
    [
        (0.0, "000111"),
        (0.25, "100011"),
        (1.0, "110001"),
    ],
)
def test_slider_changes_exact_agreement(
    scenario,
    alpha,
    expected_bits,
):
    state = build_classical_dashboard_state(
        scenario,
        alpha=alpha,
    )

    assert state["exact"]["canonical_bits"] == expected_bits


def test_b2_unavailable_changes_agreement(scenario):
    state = build_classical_dashboard_state(
        scenario,
        alpha=0.25,
        unavailable_actions={"B2"},
    )

    assert state["feasible"] is True
    assert state["exact"]["canonical_bits"] == "110001"
    assert state["unavailable_actions"] == ["B2"]
    assert "B2" not in state["exact"]["selected_actions"]


def test_dashboard_reports_no_feasible_agreement(scenario):
    state = build_classical_dashboard_state(
        scenario,
        alpha=0.25,
        unavailable_actions={"A1", "B1"},
    )

    assert state["feasible"] is False
    assert state["valid_plan_count"] == 0
    assert state["exact"] is None
    assert state["frontier"] == []
    assert state["greedy"]["valid"] is False
    assert state["simulated_annealing"]["valid"] is False


def test_selected_action_rows(scenario):
    plan = evaluate_plan(
        scenario,
        "100011",
        alpha=0.25,
    )

    rows = selected_action_rows(scenario, plan)

    assert [row["action"] for row in rows] == [
        "A1",
        "B2",
        "B3",
    ]
    assert rows[0]["satellite"] == "A-Sat-1"
    assert rows[0]["action_reserve_fraction"] == pytest.approx(
        0.1
    )
    assert selected_action_rows(scenario, None) == []


def test_company_burden_rows(scenario):
    plan = evaluate_plan(
        scenario,
        "100011",
        alpha=0.25,
    )

    rows = company_burden_rows(scenario, plan)
    by_company = {
        row["company"]: row
        for row in rows
    }

    assert by_company["Company A"]["selected_fuel"] == pytest.approx(
        2.0
    )
    assert by_company["Company B"]["selected_fuel"] == pytest.approx(
        2.0
    )
    assert by_company["Company A"][
        "reserve_burden_index"
    ] == pytest.approx(0.1)
    assert by_company["Company B"][
        "reserve_burden_index"
    ] == pytest.approx(0.553030303030303)


def test_encounter_rows_show_coverage(scenario):
    plan = evaluate_plan(
        scenario,
        "100011",
        alpha=0.25,
    )

    rows = encounter_rows(scenario, plan)
    by_encounter = {
        row["encounter"]: row
        for row in rows
    }

    assert len(rows) == 4
    assert all(row["covered"] for row in rows)
    assert by_encounter["E1"]["selected_actions"] == "A1"
    assert by_encounter["E3"]["selected_actions"] == "B2"
    assert by_encounter["E4"]["selected_actions"] == "B3"


def test_frontier_uses_current_alpha(scenario):
    state = build_classical_dashboard_state(
        scenario,
        alpha=1.0,
    )

    for plan in state["frontier"]:
        expected = evaluate_plan(
            state["scenario"],
            plan["canonical_bits"],
            alpha=1.0,
        )
        assert plan["objective_score"] == pytest.approx(
            expected["objective_score"]
        )

    rows = frontier_rows(state["frontier"])
    assert rows
    assert {
        "canonical_bits",
        "agreement",
        "fuel_total",
        "reserve_score",
        "objective_score",
    } == set(rows[0])


def test_top_quantum_sample_rows(scenario):
    rows = top_sample_rows(
        scenario,
        {
            "100011": 4,
            "000000": 3,
            "000111": 2,
        },
        alpha=0.25,
        optimal_bits={"100011"},
        limit=2,
    )

    assert len(rows) == 2
    assert rows[0]["canonical_bits"] == "100011"
    assert rows[0]["sample_rate"] == pytest.approx(4 / 9)
    assert rows[0]["valid"] is True
    assert rows[0]["optimal"] is True

    assert rows[1]["canonical_bits"] == "000000"
    assert rows[1]["valid"] is False
    assert rows[1]["optimal"] is False


@pytest.mark.parametrize(
    "bad_count",
    [-1, 1.5, True],
)
def test_invalid_sample_counts_are_rejected(
    scenario,
    bad_count,
):
    with pytest.raises(ValueError):
        top_sample_rows(
            scenario,
            {
                "100011": 10,
                "000000": bad_count,
            },
            alpha=0.25,
            limit=1,
        )


@pytest.mark.parametrize(
    "bad_limit",
    [0, -1, True, 1.5],
)
def test_invalid_sample_limit_is_rejected(
    scenario,
    bad_limit,
):
    with pytest.raises((TypeError, ValueError)):
        top_sample_rows(
            scenario,
            {"100011": 1},
            alpha=0.25,
            limit=bad_limit,
        )


def test_empty_sample_counts_are_rejected(scenario):
    with pytest.raises(ValueError):
        top_sample_rows(
            scenario,
            {},
            alpha=0.25,
        )