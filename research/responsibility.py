"""Authoritative scorer and algebra for Qubital responsibility model v1.

These are modeled priority/workload units. A response assignment does not imply
that a burn is required, jointly feasible, or physically safe. Canonical free bit
1 assigns OneWeb; 0 assigns Starlink. This differs from the original action model.
"""

from datetime import datetime, timedelta
from itertools import combinations, product
from math import isclose, isfinite
from numbers import Real

from quantum import Qubo


MODEL_ID = "qubital.responsibility.v1"
GROUPS = ("OneWeb", "Starlink")
OPTIMUM_ATOL = 1e-12


def _number(value, name, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a finite number")
    if not isfinite(value) or (positive and value <= 0):
        raise ValueError(f"{name} must be finite" + (" and positive" if positive else ""))
    return float(value)


def _identifier(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")
    return value


def _utc(value, name):
    if not isinstance(value, str):
        raise ValueError(f"{name} must be an explicitly UTC timestamp")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{name} must be an explicitly UTC timestamp") from error
    if result.tzinfo is None or result.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must be explicitly UTC")
    return result


def validate_case(case):
    """Validate the separate model schema without changing its input.

    Syntactic validity does not establish response feasibility. A case with an
    event allowing neither side is valid data but solve_exact reports infeasible.
    """
    if not isinstance(case, dict) or case.get("model_id") != MODEL_ID:
        raise ValueError(f"model_id must be {MODEL_ID}")
    start = _utc(case["horizon_start"], "horizon_start")
    end = _utc(case["horizon_end"], "horizon_end")
    if end < start:
        raise ValueError("horizon_end precedes horizon_start")
    events, background = case["events"], case["background"]
    if not isinstance(events, list) or not isinstance(background, list):
        raise TypeError("events and background must be lists")
    identities, pairs, satellite_groups, weights = set(), set(), {}, []

    def record_id(record):
        identity = _identifier(record["event_id"], "event_id")
        if identity in identities:
            raise ValueError("duplicate event_id")
        identities.add(identity)
        tca = _utc(record["tca"], "tca")
        if not start <= tca <= end:
            raise ValueError("record TCA falls outside the frozen case horizon")
        weights.append(_number(record["weight"], "weight", positive=True))
        return tca

    for event in events:
        tca = record_id(event)
        oneweb = _identifier(event["oneweb_id"], "oneweb_id")
        starlink = _identifier(event["starlink_id"], "starlink_id")
        pair = (oneweb, starlink, tca)
        if pair in pairs:
            raise ValueError("duplicate canonical satellite pair plus TCA")
        pairs.add(pair)
        for satellite, group in ((oneweb, "OneWeb"), (starlink, "Starlink")):
            if satellite in satellite_groups and satellite_groups[satellite] != group:
                raise ValueError("satellite identity belongs to conflicting groups")
            satellite_groups[satellite] = group
        for field in ("oneweb_allowed", "starlink_allowed"):
            if type(event[field]) is not bool:
                raise TypeError(f"{field} must be an explicit modeled boolean")
    background_pairs = set()
    for event in background:
        tca = record_id(event)
        satellite = _identifier(event["satellite_id"], "satellite_id")
        if event["group"] not in GROUPS or satellite_groups.get(satellite) != event["group"]:
            raise ValueError("background must belong to a selected active satellite and group")
        if event["object_type"] != "DEB" or event["catalog_confirmed"] is not True:
            raise ValueError("background requires catalog-confirmed DEB classification")
        pair = (satellite, _identifier(event["debris_id"], "debris_id"), tca)
        if pair in background_pairs:
            raise ValueError("duplicate background satellite pair plus TCA")
        background_pairs.add(pair)
    reference = _number(case["W_ref"], "W_ref", positive=True)
    total = sum(weights)
    if not isfinite(total) or (reference < total and not isclose(reference, total, rel_tol=1e-12, abs_tol=1e-12)):
        raise ValueError("W_ref must bound all active and aligned background weights")
    return case


def _free_events(case):
    return [event for event in case["events"] if event["oneweb_allowed"] and event["starlink_allowed"]]


def free_event_ids(case):
    validate_case(case)
    return tuple(event["event_id"] for event in _free_events(case))


def _feasible(case):
    return all(event["oneweb_allowed"] or event["starlink_allowed"] for event in case["events"])


def _eta(eta):
    result = _number(eta, "eta")
    if not 0 <= result <= 1:
        raise ValueError("eta must be in [0,1]")
    return result


def _background_flag(background):
    if type(background) is not bool:
        raise TypeError("background must be boolean")


def evaluate_assignment(case, canonical_bits, eta=.5, background=True):
    """Score free bits through direct burden accumulation, without QUBO algebra."""
    validate_case(case)
    eta = _eta(eta)
    _background_flag(background)
    if not _feasible(case):
        raise ValueError("no allowed response exists for at least one event")
    free = _free_events(case)
    if not isinstance(canonical_bits, str):
        raise TypeError("canonical_bits must be a string of free-event bits")
    if len(canonical_bits) != len(free) or any(bit not in "01" for bit in canonical_bits):
        raise ValueError(f"canonical_bits must contain exactly {len(free)} binary digits")
    choices = dict(zip((event["event_id"] for event in free), canonical_bits))
    fleets = {group: 0.0 for group in GROUPS}
    satellites = {event[key]: 0.0 for event in case["events"] for key in ("oneweb_id", "starlink_id")}
    if background:
        for record in case["background"]:
            fleets[record["group"]] += record["weight"]
            satellites[record["satellite_id"]] += record["weight"]
    full_bits, assignments = [], []
    for event in case["events"]:
        bit = choices.get(event["event_id"], "1" if event["oneweb_allowed"] else "0")
        group = "OneWeb" if bit == "1" else "Starlink"
        satellite = event["oneweb_id"] if bit == "1" else event["starlink_id"]
        fleets[group] += event["weight"]
        satellites[satellite] += event["weight"]
        full_bits.append(bit)
        assignments.append({"event_id": event["event_id"], "group": group, "satellite_id": satellite})
    # Normalize before squaring to avoid overflow on large finite input scales.
    reference = case["W_ref"]
    fleet_score = sum((burden / reference)**2 for burden in fleets.values())
    satellite_score = sum((burden / reference)**2 for burden in satellites.values())
    return {"model_id": MODEL_ID, "canonical_bits": canonical_bits, "full_bits": "".join(full_bits),
            "fleet_burdens": fleets, "satellite_burdens": satellites, "assignments": assignments,
            "fleet_concentration": fleet_score, "satellite_concentration": satellite_score,
            "objective_score": (1 - eta) * fleet_score + eta * satellite_score,
            "valid": True, "eta": eta, "background_enabled": background}


def build_responsibility_qubo(case, eta=.5, background=True):
    """Independently expand affine burdens with binary y_i²=y_i.

    An all-fixed case returns a zero-variable constant Qubo. Evaluate it directly;
    do not convert it into a zero-qubit operator or run QAOA.
    """
    validate_case(case)
    eta = _eta(eta)
    _background_flag(background)
    if not _feasible(case):
        raise ValueError("cannot encode a case with no allowed response")
    free = _free_events(case)
    indices = {event["event_id"]: i for i, event in enumerate(free)}
    components = {("fleet", group): [0.0, {}] for group in GROUPS}
    components.update({("satellite", event[key]): [0.0, {}]
                       for event in case["events"] for key in ("oneweb_id", "starlink_id")})

    def add(group, satellite, constant, index=None, coefficient=0.0):
        for component in (("fleet", group), ("satellite", satellite)):
            affine = components[component]
            affine[0] += constant
            if index is not None:
                affine[1][index] = affine[1].get(index, 0.0) + coefficient

    if background:
        for record in case["background"]:
            add(record["group"], record["satellite_id"], record["weight"])
    for event in case["events"]:
        weight = event["weight"]
        if event["event_id"] in indices:
            i = indices[event["event_id"]]
            add("Starlink", event["starlink_id"], weight, i, -weight)
            add("OneWeb", event["oneweb_id"], 0.0, i, weight)
        elif event["oneweb_allowed"]:
            add("OneWeb", event["oneweb_id"], weight)
        else:
            add("Starlink", event["starlink_id"], weight)
    constant, linear, quadratic = 0.0, [0.0] * len(free), {}
    for (kind, _), (a, coefficients) in components.items():
        multiplier = 1 - eta if kind == "fleet" else eta
        a /= case["W_ref"]
        b = {i: value / case["W_ref"] for i, value in coefficients.items()}
        constant += multiplier * a * a
        for i, value in b.items():
            linear[i] += multiplier * (2 * a * value + value * value)
        for i, j in combinations(sorted(b), 2):
            quadratic[i, j] = quadratic.get((i, j), 0.0) + multiplier * 2 * b[i] * b[j]
    return Qubo(tuple(event["event_id"] for event in free), constant, tuple(linear), quadratic)


def solve_exact(case, eta=.5, background=True):
    """Enumerate through this model's scorer and retain every tied optimum."""
    validate_case(case)
    eta = _eta(eta)
    _background_flag(background)
    if not _feasible(case):
        return {"status": "infeasible", "optimal_bits": [], "optimal_full_bits": [],
                "minimum_score": None, "evaluations": 0}
    width = len(_free_events(case))
    plans = [evaluate_assignment(case, "".join(bits), eta, background)
             for bits in product("01", repeat=width)]
    best = min(plan["objective_score"] for plan in plans)
    optimal = [plan for plan in plans if isclose(plan["objective_score"], best, rel_tol=0, abs_tol=OPTIMUM_ATOL)]
    return {"status": "deterministic" if width == 0 else "feasible",
            "optimal_bits": [plan["canonical_bits"] for plan in optimal],
            "optimal_full_bits": [plan["full_bits"] for plan in optimal],
            "minimum_score": best, "evaluations": len(plans)}
