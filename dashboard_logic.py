"""Pure, testable dashboard logic for Qubital."""

from __future__ import annotations

import copy
from collections.abc import Collection, Mapping
from numbers import Integral

from classical import (
    enumerate_plans,
    pareto_frontier,
    solve_exact,
    solve_greedy,
    solve_simulated_annealing,
)
from scoring import evaluate_plan


def scenario_with_unavailable_actions(
    scenario: dict,
    unavailable_actions: Collection[str] = (),
) -> dict:
    """Return a copied scenario with the requested actions unavailable."""
    changed = copy.deepcopy(scenario)
    unavailable = set(unavailable_actions)

    action_ids = {
        action["id"]
        for action in changed["actions"]
    }
    unknown = unavailable - action_ids
    if unknown:
        raise ValueError(
            f"Unknown unavailable actions: {sorted(unknown)}"
        )

    for action in changed["actions"]:
        action["available"] = action["id"] not in unavailable

    return changed


def build_classical_dashboard_state(
    scenario: dict,
    alpha: float,
    unavailable_actions: Collection[str] = (),
    *,
    annealing_seed: int = 42,
) -> dict:
    """Compute the complete classical state shown by the dashboard."""
    adjusted = scenario_with_unavailable_actions(
        scenario,
        unavailable_actions,
    )

    plans = enumerate_plans(adjusted, alpha)
    valid_plans = [
        plan
        for plan in plans
        if plan["valid"]
    ]

    exact = solve_exact(adjusted, alpha)
    greedy = solve_greedy(adjusted, alpha)
    annealed = solve_simulated_annealing(
        adjusted,
        alpha,
        seed=annealing_seed,
    )

    return {
        "scenario": adjusted,
        "alpha": alpha,
        "unavailable_actions": [
            action_id
            for action_id in adjusted["action_order"]
            if action_id in set(unavailable_actions)
        ],
        "total_plan_count": len(plans),
        "valid_plan_count": len(valid_plans),
        "feasible": exact is not None,
        "exact": exact,
        "greedy": greedy,
        "simulated_annealing": annealed,
        "frontier": [evaluate_plan(adjusted,plan["canonical_bits"], alpha,) for plan in pareto_frontier(adjusted)],
    }


def selected_action_rows(
    scenario: dict,
    plan: dict | None,
) -> list[dict]:
    """Return presentation-ready details for a selected agreement."""
    if plan is None:
        return []

    actions_by_id = {
        action["id"]: action
        for action in scenario["actions"]
    }
    rows = []

    for action_id in plan["selected_actions"]:
        action = actions_by_id[action_id]
        rows.append(
            {
                "action": action["id"],
                "satellite": action["satellite"],
                "company": action["company"],
                "fuel": action["fuel"],
                "remaining_reserve": action["remaining_reserve"],
                "action_reserve_fraction": (
                    action["fuel"]
                    / action["remaining_reserve"]
                ),
                "covers": ", ".join(action["covers"]),
            }
        )

    return rows


def company_burden_rows(
    scenario: dict,
    plan: dict | None,
) -> list[dict]:
    """Summarize selected fuel and reserve-burden index by company."""
    actions_by_id = {
        action["id"]: action
        for action in scenario["actions"]
    }

    fuel_by_company = {
        company: 0.0
        for company in scenario["companies"]
    }
    burden_by_company = {
        company: 0.0
        for company in scenario["companies"]
    }

    if plan is not None:
        burden_by_company.update(plan["company_burdens"])

        for action_id in plan["selected_actions"]:
            action = actions_by_id[action_id]
            fuel_by_company[action["company"]] += action["fuel"]

    return [
        {
            "company": company,
            "selected_fuel": fuel_by_company[company],
            "reserve_burden_index": burden_by_company[company],
        }
        for company in scenario["companies"]
    ]


def encounter_rows(
    scenario: dict,
    plan: dict | None,
) -> list[dict]:
    """Show which candidate actions cover each modeled encounter."""
    selected = (
        set(plan["selected_actions"])
        if plan is not None
        else set()
    )
    rows = []

    for encounter in scenario["encounters"]:
        candidates = [
            action["id"]
            for action in scenario["actions"]
            if encounter in action["covers"]
        ]
        selected_candidates = [
            action_id
            for action_id in candidates
            if action_id in selected
        ]

        rows.append(
            {
                "encounter": encounter,
                "candidate_actions": ", ".join(candidates),
                "selected_actions": (
                    ", ".join(selected_candidates)
                    if selected_candidates
                    else "None"
                ),
                "covered": bool(selected_candidates),
            }
        )

    return rows


def frontier_rows(frontier: list[dict]) -> list[dict]:
    """Convert Pareto-frontier plans into chart-ready records."""
    return [
        {
            "canonical_bits": plan["canonical_bits"],
            "agreement": " + ".join(plan["selected_actions"]),
            "fuel_total": plan["fuel_total"],
            "reserve_score": plan["reserve_score"],
            "objective_score": plan["objective_score"],
        }
        for plan in frontier
    ]


def top_sample_rows(
    scenario: dict,
    canonical_counts: Mapping[str, int],
    alpha: float,
    *,
    optimal_bits: Collection[str] = (),
    limit: int = 10,
) -> list[dict]:
    """Score the most frequently sampled canonical quantum plans."""
    if isinstance(limit, bool) or not isinstance(limit, Integral):
        raise TypeError("limit must be a positive integer")

    if limit < 1:
        raise ValueError("limit must be a positive integer")

    for count in canonical_counts.values():
        if (
            isinstance(count, bool)
            or not isinstance(count, Integral)
            or count < 0
        ):
            raise ValueError(
                "sample counts must be nonnegative integers"
            )

    total_shots = sum(canonical_counts.values())
    if total_shots <= 0:
        raise ValueError(
            "canonical_counts must contain at least one shot"
        )

    optimal = set(optimal_bits)
    ordered_counts = sorted(
        canonical_counts.items(),
        key=lambda item: (-item[1], item[0]),
    )

    rows = []
    for bits, count in ordered_counts[:limit]:
        plan = evaluate_plan(scenario, bits, alpha)

        rows.append(
            {
                "canonical_bits": bits,
                "agreement": (
                    " + ".join(plan["selected_actions"])
                    if plan["selected_actions"]
                    else "No actions"
                ),
                "count": int(count),
                "sample_rate": int(count) / total_shots,
                "valid": plan["valid"],
                "optimal": bits in optimal,
                "fuel_total": plan["fuel_total"],
                "reserve_score": plan["reserve_score"],
                "objective_score": plan["objective_score"],
            }
        )

    return rows