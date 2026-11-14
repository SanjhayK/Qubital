import copy
import itertools
import math

import pytest

from scoring import evaluate_plan, load_scenario


@pytest.fixture
def scenario():
    return load_scenario("data/original.json")


def all_plans(scenario, alpha=None):
    plans = []

    for bits_tuple in itertools.product(
        "01",
        repeat=len(scenario["action_order"]),
    ):
        bits = "".join(bits_tuple)
        plans.append(evaluate_plan(scenario, bits, alpha))

    return plans


def best_valid_plan(scenario, alpha=None):
    valid_plans = [
        plan
        for plan in all_plans(scenario, alpha)
        if plan["valid"]
    ]
    return min(valid_plans, key=lambda plan: plan["objective_score"])


def test_scenario_loads(scenario):
    assert scenario["action_order"] == [
        "A1",
        "A2",
        "A3",
        "B1",
        "B2",
        "B3",
    ]


def test_there_are_64_total_and_24_valid_plans(scenario):
    plans = all_plans(scenario)

    assert len(plans) == 64
    assert sum(plan["valid"] for plan in plans) == 24


def test_cheapest_company_b_plan(scenario):
    result = evaluate_plan(scenario, "000111", alpha=0.0)

    assert result["selected_actions"] == ["B1", "B2", "B3"]
    assert result["fuel_total"] == pytest.approx(3.0)
    assert result["company_burdens"]["Company A"] == pytest.approx(0.0)
    assert result["company_burdens"]["Company B"] == pytest.approx(
        0.803030303030303
    )
    assert result["valid"] is True


def test_default_tradeoff_plan(scenario):
    result = evaluate_plan(scenario, "100011", alpha=0.25)

    assert result["selected_actions"] == ["A1", "B2", "B3"]
    assert result["fuel_total"] == pytest.approx(4.0)
    assert result["company_burdens"]["Company A"] == pytest.approx(0.1)
    assert result["company_burdens"]["Company B"] == pytest.approx(
        0.553030303030303
    )
    assert result["valid"] is True


def test_reserve_focused_plan(scenario):
    result = evaluate_plan(scenario, "110001", alpha=1.0)

    assert result["selected_actions"] == ["A1", "A2", "B3"]
    assert result["fuel_total"] == pytest.approx(5.0)
    assert result["company_burdens"]["Company A"] == pytest.approx(0.225)
    assert result["company_burdens"]["Company B"] == pytest.approx(0.25)
    assert result["valid"] is True


@pytest.mark.parametrize(
    ("alpha", "expected_bits"),
    [
        (0.0, "000111"),
        (0.25, "100011"),
        (1.0, "110001"),
    ],
)
def test_expected_optimum_for_each_alpha(
    scenario,
    alpha,
    expected_bits,
):
    best = best_valid_plan(scenario, alpha)

    assert best["canonical_bits"] == expected_bits


def test_uncovered_encounters_make_plan_invalid(scenario):
    result = evaluate_plan(scenario, "000000")

    assert result["valid"] is False
    assert result["uncovered_encounters"] == [
        "E1",
        "E2",
        "E3",
        "E4",
    ]
    assert result["unavailable_selected"] == []


def test_unavailable_action_makes_plan_invalid(scenario):
    changed = copy.deepcopy(scenario)

    for action in changed["actions"]:
        if action["id"] == "B2":
            action["available"] = False

    result = evaluate_plan(changed, "000111")

    assert result["valid"] is False
    assert result["unavailable_selected"] == ["B2"]


def test_best_plan_when_b2_is_unavailable(scenario):
    changed = copy.deepcopy(scenario)

    for action in changed["actions"]:
        if action["id"] == "B2":
            action["available"] = False

    best = best_valid_plan(changed, alpha=0.25)

    assert best["canonical_bits"] == "110001"


def test_no_valid_plan_when_a1_and_b1_are_unavailable(scenario):
    changed = copy.deepcopy(scenario)

    for action in changed["actions"]:
        if action["id"] in {"A1", "B1"}:
            action["available"] = False

    valid_plans = [
        plan
        for plan in all_plans(changed, alpha=0.25)
        if plan["valid"]
    ]

    assert valid_plans == []


def test_evaluation_does_not_modify_scenario(scenario):
    original = copy.deepcopy(scenario)

    evaluate_plan(scenario, "100011", alpha=0.25)

    assert scenario == original


@pytest.mark.parametrize(
    "bad_bits",
    [
        "10001",
        "1000111",
        "10001x",
        "",
    ],
)
def test_invalid_bit_strings_are_rejected(scenario, bad_bits):
    with pytest.raises(ValueError):
        evaluate_plan(scenario, bad_bits)


@pytest.mark.parametrize("bad_alpha", [-0.01, 1.01])
def test_out_of_range_alpha_is_rejected(scenario, bad_alpha):
    with pytest.raises(ValueError):
        evaluate_plan(scenario, "100011", alpha=bad_alpha)


def test_scores_follow_the_documented_formula(scenario):
    result = evaluate_plan(scenario, "100011", alpha=0.25)

    expected_reserve_score = 0.1**2 + 0.553030303030303**2
    expected_preference = (
        0.75 * (4.0 / 9.0)
        + 0.25 * (
            expected_reserve_score / 0.8254830119
        )
    )

    assert result["reserve_score"] == pytest.approx(
        expected_reserve_score
    )
    assert result["preference_score"] == pytest.approx(
        expected_preference
    )
    assert result["objective_score"] == pytest.approx(
        expected_preference
    )