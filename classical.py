"""Classical optimization baselines for Qubital."""

from __future__ import annotations

import itertools
import math
import random

from scoring import evaluate_plan


def enumerate_plans(
    scenario: dict,
    alpha: float | None = None,
) -> list[dict]:
    """Evaluate every possible canonical plan."""
    number_of_actions = len(scenario["action_order"])
    plans = []

    for bit_tuple in itertools.product("01", repeat=number_of_actions):
        canonical_bits = "".join(bit_tuple)
        plans.append(
            evaluate_plan(
                scenario,
                canonical_bits,
                alpha,
            )
        )

    return plans


def _plan_rank(plan: dict) -> tuple:
    """Provide deterministic tie-breaking between plans."""
    return (
        plan["objective_score"],
        plan["fuel_total"],
        plan["reserve_score"],
        plan["canonical_bits"],
    )


def solve_exact(
    scenario: dict,
    alpha: float | None = None,
) -> dict | None:
    """Return the best valid plan using exhaustive enumeration.

    Returns None when no valid agreement exists.
    """
    valid_plans = [
        plan
        for plan in enumerate_plans(scenario, alpha)
        if plan["valid"]
    ]

    if not valid_plans:
        return None

    return min(valid_plans, key=_plan_rank)


def solve_greedy(
    scenario: dict,
    alpha: float | None = None,
) -> dict:
    """Build an agreement one action at a time.

    At each step, this baseline selects the available action that covers
    a currently uncovered encounter and produces the lowest immediate
    objective score. It then removes any redundant selected actions.

    The returned plan may be invalid if the scenario has no feasible
    agreement.
    """
    number_of_actions = len(scenario["action_order"])
    bits = ["0"] * number_of_actions

    actions_by_id = {
        action["id"]: action
        for action in scenario["actions"]
    }

    current = evaluate_plan(
        scenario,
        "".join(bits),
        alpha,
    )

    while not current["valid"]:
        uncovered = set(current["uncovered_encounters"])
        candidates = []

        for index, action_id in enumerate(scenario["action_order"]):
            action = actions_by_id[action_id]

            if bits[index] == "1":
                continue

            if not action["available"]:
                continue

            if not uncovered.intersection(action["covers"]):
                continue

            candidate_bits = bits.copy()
            candidate_bits[index] = "1"

            candidate = evaluate_plan(
                scenario,
                "".join(candidate_bits),
                alpha,
            )
            candidates.append((candidate, candidate_bits))

        if not candidates:
            return current

        best_candidate, best_bits = min(
            candidates,
            key=lambda item: _plan_rank(item[0]),
        )

        bits = best_bits
        current = best_candidate

    # Remove selected actions that are no longer necessary.
    improved = True
    while improved:
        improved = False

        for index, bit in enumerate(bits):
            if bit != "1":
                continue

            candidate_bits = bits.copy()
            candidate_bits[index] = "0"
            candidate = evaluate_plan(
                scenario,
                "".join(candidate_bits),
                alpha,
            )

            if (
                candidate["valid"]
                and _plan_rank(candidate) < _plan_rank(current)
            ):
                bits = candidate_bits
                current = candidate
                improved = True
                break

    return current


def solve_simulated_annealing(
    scenario: dict,
    alpha: float | None = None,
    *,
    seed: int = 0,
    restarts: int = 12,
    steps_per_restart: int = 500,
    initial_temperature: float = 2.0,
    cooling_rate: float = 0.99,
) -> dict:
    """Search for a low-scoring plan using simulated annealing.

    The random seed makes experiment runs reproducible. If at least one
    valid plan is discovered, the best valid plan is returned. Otherwise,
    the best invalid plan found is returned so callers can report that no
    valid agreement was discovered.
    """
    if restarts <= 0:
        raise ValueError("restarts must be positive")

    if steps_per_restart <= 0:
        raise ValueError("steps_per_restart must be positive")

    if initial_temperature <= 0:
        raise ValueError("initial_temperature must be positive")

    if not 0 < cooling_rate <= 1:
        raise ValueError("cooling_rate must be greater than 0 and at most 1")

    rng = random.Random(seed)
    number_of_actions = len(scenario["action_order"])

    best_overall = None
    best_valid = None

    for _ in range(restarts):
        bits = [
            rng.choice(("0", "1"))
            for _ in range(number_of_actions)
        ]
        current = evaluate_plan(
            scenario,
            "".join(bits),
            alpha,
        )

        if best_overall is None or _plan_rank(current) < _plan_rank(
            best_overall
        ):
            best_overall = current

        if current["valid"] and (
            best_valid is None
            or _plan_rank(current) < _plan_rank(best_valid)
        ):
            best_valid = current

        temperature = initial_temperature

        for _ in range(steps_per_restart):
            flip_index = rng.randrange(number_of_actions)
            candidate_bits = bits.copy()
            candidate_bits[flip_index] = (
                "0"
                if candidate_bits[flip_index] == "1"
                else "1"
            )

            candidate = evaluate_plan(
                scenario,
                "".join(candidate_bits),
                alpha,
            )

            score_change = (
                candidate["objective_score"]
                - current["objective_score"]
            )

            accept = score_change <= 0
            if not accept:
                probability = math.exp(
                    -score_change / max(temperature, 1e-12)
                )
                accept = rng.random() < probability

            if accept:
                bits = candidate_bits
                current = candidate

            if _plan_rank(current) < _plan_rank(best_overall):
                best_overall = current

            if current["valid"] and (
                best_valid is None
                or _plan_rank(current) < _plan_rank(best_valid)
            ):
                best_valid = current

            temperature *= cooling_rate

    if best_valid is not None:
        return best_valid

    # At least one state is always evaluated because restarts is positive.
    return best_overall


def pareto_frontier(scenario: dict) -> list[dict]:
    """Return valid plans not dominated on fuel and reserve burden.

    Plan A dominates plan B when A uses no more fuel and has no greater
    reserve score, with a strict improvement in at least one measure.
    Equal tradeoff points remain in the result because they can represent
    distinct agreements that operators may negotiate over.
    """
    valid_plans = [
        plan
        for plan in enumerate_plans(scenario)
        if plan["valid"]
    ]
    frontier = []

    for candidate in valid_plans:
        dominated = any(
            other["canonical_bits"] != candidate["canonical_bits"]
            and other["fuel_total"] <= candidate["fuel_total"]
            and other["reserve_score"] <= candidate["reserve_score"]
            and (
                other["fuel_total"] < candidate["fuel_total"]
                or other["reserve_score"] < candidate["reserve_score"]
            )
            for other in valid_plans
        )

        if not dominated:
            frontier.append(candidate)

    return sorted(
        frontier,
        key=lambda plan: (
            plan["fuel_total"],
            plan["reserve_score"],
            plan["canonical_bits"],
        ),
    )