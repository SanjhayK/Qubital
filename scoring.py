"""Authoritative scoring logic for Qubital maneuver agreements."""

import json
from pathlib import Path


def load_scenario(path: str | Path) -> dict:
    """Load and validate a Qubital scenario JSON file."""
    with Path(path).open("r", encoding="utf-8") as file:
        scenario = json.load(file)

    required_keys = {
        "action_order",
        "companies",
        "encounters",
        "actions",
        "objective",
    }
    missing = required_keys - scenario.keys()
    if missing:
        raise ValueError(f"Scenario is missing required keys: {sorted(missing)}")

    action_order = scenario["action_order"]
    actions = scenario["actions"]
    action_ids = [action["id"] for action in actions]

    if len(action_order) != len(set(action_order)):
        raise ValueError("action_order contains duplicate action IDs")

    if set(action_order) != set(action_ids):
        raise ValueError("action_order must contain every action ID exactly once")

    if len(action_ids) != len(set(action_ids)):
        raise ValueError("actions contains duplicate action IDs")

    companies = set(scenario["companies"])
    encounters = set(scenario["encounters"])

    for action in actions:
        required_action_keys = {
            "id",
            "satellite",
            "company",
            "fuel",
            "remaining_reserve",
            "covers",
            "available",
        }
        missing_action_keys = required_action_keys - action.keys()
        if missing_action_keys:
            raise ValueError(
                f"Action {action.get('id', '<unknown>')} is missing keys: "
                f"{sorted(missing_action_keys)}"
            )

        if action["company"] not in companies:
            raise ValueError(
                f"Action {action['id']} refers to an unknown company"
            )

        if action["fuel"] < 0:
            raise ValueError(f"Action {action['id']} has negative fuel")

        if action["remaining_reserve"] <= 0:
            raise ValueError(
                f"Action {action['id']} must have positive remaining reserve"
            )

        unknown_encounters = set(action["covers"]) - encounters
        if unknown_encounters:
            raise ValueError(
                f"Action {action['id']} covers unknown encounters: "
                f"{sorted(unknown_encounters)}"
            )

        if not isinstance(action["available"], bool):
            raise ValueError(
                f"Action {action['id']} availability must be true or false"
            )

    objective = scenario["objective"]
    required_objective_keys = {
        "fuel_normalization",
        "reserve_normalization",
        "violation_penalty",
        "default_alpha",
    }
    missing_objective_keys = required_objective_keys - objective.keys()
    if missing_objective_keys:
        raise ValueError(
            f"Objective is missing keys: {sorted(missing_objective_keys)}"
        )

    if objective["fuel_normalization"] <= 0:
        raise ValueError("fuel_normalization must be positive")

    if objective["reserve_normalization"] <= 0:
        raise ValueError("reserve_normalization must be positive")

    if objective["violation_penalty"] <= 0:
        raise ValueError("violation_penalty must be positive")

    if not 0 <= objective["default_alpha"] <= 1:
        raise ValueError("default_alpha must be between 0 and 1")

    # Verify that the declared reserve normalization is a valid upper bound.
    maximum_company_burdens = {company: 0.0 for company in scenario["companies"]}
    for action in actions:
        maximum_company_burdens[action["company"]] += (
            action["fuel"] / action["remaining_reserve"]
        )

    exact_reserve_bound = sum(
        burden**2 for burden in maximum_company_burdens.values()
    )
    declared_reserve_bound = objective["reserve_normalization"]

    if declared_reserve_bound + 1e-12 < exact_reserve_bound:
        raise ValueError(
            "reserve_normalization is smaller than the all-actions reserve bound"
        )

    return scenario


def evaluate_plan(
    scenario: dict,
    canonical_bits: str,
    alpha: float | None = None,
) -> dict:
    """Evaluate one canonical maneuver agreement under the modeled rules."""
    action_order = scenario["action_order"]

    if not isinstance(canonical_bits, str):
        raise TypeError("canonical_bits must be a string")

    if len(canonical_bits) != len(action_order):
        raise ValueError(
            f"canonical_bits must contain exactly {len(action_order)} bits"
        )

    if any(bit not in "01" for bit in canonical_bits):
        raise ValueError("canonical_bits may contain only 0 and 1")

    if alpha is None:
        alpha = scenario["objective"]["default_alpha"]

    if isinstance(alpha, bool) or not isinstance(alpha, (int, float)):
        raise TypeError("alpha must be a number between 0 and 1")

    if not 0 <= alpha <= 1:
        raise ValueError("alpha must be between 0 and 1")

    actions_by_id = {
        action["id"]: action
        for action in scenario["actions"]
    }

    selected_actions = [
        action_id
        for action_id, bit in zip(action_order, canonical_bits)
        if bit == "1"
    ]
    selected_records = [
        actions_by_id[action_id]
        for action_id in selected_actions
    ]

    fuel_total = sum(action["fuel"] for action in selected_records)

    company_burdens = {
        company: 0.0
        for company in scenario["companies"]
    }
    for action in selected_records:
        company_burdens[action["company"]] += (
            action["fuel"] / action["remaining_reserve"]
        )

    reserve_score = sum(
        burden**2 for burden in company_burdens.values()
    )

    covered_encounters = {
        encounter
        for action in selected_records
        for encounter in action["covers"]
    }
    uncovered_encounters = [
        encounter
        for encounter in scenario["encounters"]
        if encounter not in covered_encounters
    ]

    unavailable_selected = [
        action["id"]
        for action in selected_records
        if not action["available"]
    ]

    valid = not uncovered_encounters and not unavailable_selected

    objective = scenario["objective"]
    preference_score = (
        (1 - alpha)
        * fuel_total
        / objective["fuel_normalization"]
        + alpha
        * reserve_score
        / objective["reserve_normalization"]
    )

    violation_count = (
        len(uncovered_encounters)
        + len(unavailable_selected)
    )
    objective_score = (
        preference_score
        + objective["violation_penalty"] * violation_count
    )

    return {
        "canonical_bits": canonical_bits,
        "selected_actions": selected_actions,
        "fuel_total": fuel_total,
        "company_burdens": company_burdens,
        "reserve_score": reserve_score,
        "uncovered_encounters": uncovered_encounters,
        "unavailable_selected": unavailable_selected,
        "valid": valid,
        "preference_score": preference_score,
        "objective_score": objective_score,
    }