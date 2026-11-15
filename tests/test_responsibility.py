"""Synthetic correctness fixtures for the separate responsibility model.

These fixtures are not SOCRATES rows or evidence of real-data selection.
"""

import copy
from itertools import product

import numpy as np
import pytest
from qiskit.quantum_info import Statevector

from quantum import qubo_to_ising
from research.responsibility import (
    MODEL_ID,
    build_responsibility_qubo,
    evaluate_assignment,
    free_event_ids,
    solve_exact,
    validate_case,
)


def synthetic_case(priority=False):
    weights = [1, .7, .4, .3, .2, .1] if priority else [1] * 6
    records = [("O1", "S1", "01:00:00"), ("O1", "S2", "01:00:02.844"),
               ("O2", "S1", "02:00:00"), ("O3", "S2", "03:00:00"),
               ("O4", "S3", "04:00:00"), ("O2", "S3", "05:00:00")]
    events = [{"event_id": f"synthetic-E{i}", "oneweb_id": oneweb, "starlink_id": starlink,
               "tca": f"2026-11-15T{time}Z", "weight": weight,
               "oneweb_allowed": True, "starlink_allowed": True}
              for i, ((oneweb, starlink, time), weight) in enumerate(zip(records, weights))]
    background = [{"event_id": f"synthetic-D{i}", "tca": f"2026-11-15T0{i+1}:30:00Z",
                   "group": "OneWeb", "satellite_id": satellite, "weight": weight,
                   "object_type": "DEB", "catalog_confirmed": True, "debris_id": f"DEB{i}"}
                  for i, (satellite, weight) in enumerate(zip(("O1", "O2"), (.6, .2) if priority else (1, 1)))]
    return {"model_id": MODEL_ID, "horizon_start": "2026-11-15T00:00:00Z",
            "horizon_end": "2026-11-15T06:00:00Z", "events": events,
            "background": background,
            "W_ref": sum(weights) + sum(record["weight"] for record in background)}


@pytest.mark.parametrize("priority", [False, True])
@pytest.mark.parametrize("background", [False, True])
def test_all_64_direct_qubo_and_ising_energies(priority, background):
    case = synthetic_case(priority)
    before = copy.deepcopy(case)
    qubo = build_responsibility_qubo(case, eta=.5, background=background)
    cost = qubo_to_ising(qubo)
    for bits in product("01", repeat=6):
        canonical = "".join(bits)
        direct = evaluate_assignment(case, canonical, eta=.5, background=background)
        basis = Statevector.from_int(int(canonical[::-1], 2), 64)
        energy = basis.expectation_value(cost.operator).real + cost.offset
        assert qubo.evaluate(canonical) == pytest.approx(direct["objective_score"], rel=0, abs=1e-12)
        assert energy == pytest.approx(direct["objective_score"], rel=0, abs=1e-12)
        assert direct["full_bits"] == canonical and direct["valid"]
    assert case == before


def two_shared_events():
    case = synthetic_case()
    case["events"] = case["events"][:2]
    case["background"] = case["background"][:1]
    case["background"][0]["weight"] = 2
    case["W_ref"] = 4
    return case


def test_independent_shared_satellite_and_background_constant_anchors():
    case = two_shared_events()
    expected_off = {"00": .1875, "01": .125, "10": .125, "11": .25}
    expected_on = {"00": .4375, "01": .625, "10": .625, "11": 1}
    for bits in expected_off:
        assert evaluate_assignment(case, bits, background=False)["objective_score"] == expected_off[bits]
        assert evaluate_assignment(case, bits, background=True)["objective_score"] == expected_on[bits]
    qubo = build_responsibility_qubo(case)
    assert qubo.constant == .4375
    assert qubo.linear == (.1875, .1875)
    assert qubo.quadratic == {(0, 1): .1875}
    # Zero means all Starlink, not an empty maneuver-action set.
    plan = evaluate_assignment(case, "00")
    assert plan["fleet_burdens"] == {"OneWeb": 2, "Starlink": 2}


def test_fixed_oneweb_response_retains_burden_and_reduced_constant():
    case = two_shared_events()
    case["events"][0]["starlink_allowed"] = False
    assert free_event_ids(case) == ("synthetic-E1",)
    qubo = build_responsibility_qubo(case)
    assert qubo.constant == .625
    assert qubo.linear == (.375,)
    assert qubo.quadratic == {}
    for bits, full in (("0", "10"), ("1", "11")):
        plan = evaluate_assignment(case, bits)
        assert plan["full_bits"] == full
        assert qubo.evaluate(bits) == plan["objective_score"]


@pytest.mark.parametrize("eta", [0, .5, 1])
def test_fixed_both_sides_reduction_preserves_all_ising_basis_offsets(eta):
    case = synthetic_case(priority=True)
    case["events"][0]["starlink_allowed"] = False
    case["events"][1]["oneweb_allowed"] = False
    qubo = build_responsibility_qubo(case, eta=eta)
    cost = qubo_to_ising(qubo)
    assert len(qubo.action_order) == 4
    for bits in product("01", repeat=4):
        canonical = "".join(bits)
        direct = evaluate_assignment(case, canonical, eta=eta)
        basis = Statevector.from_int(int(canonical[::-1], 2), 16)
        assert direct["full_bits"] == "10" + canonical
        assert qubo.evaluate(canonical) == pytest.approx(direct["objective_score"], rel=0, abs=1e-12)
        assert basis.expectation_value(cost.operator).real + cost.offset == pytest.approx(
            direct["objective_score"], rel=0, abs=1e-12
        )


def test_all_fixed_returns_deterministic_result_without_quantum_execution():
    case = two_shared_events()
    case["events"][0]["starlink_allowed"] = False
    case["events"][1]["oneweb_allowed"] = False
    result = solve_exact(case)
    assert result == {"status": "deterministic", "optimal_bits": [""],
                      "optimal_full_bits": ["10"], "minimum_score": .625, "evaluations": 1}
    qubo = build_responsibility_qubo(case)
    assert qubo.action_order == () and qubo.evaluate("") == .625


def test_neither_side_allowed_is_infeasible_not_a_penalized_optimum():
    case = two_shared_events()
    case["events"][0].update(oneweb_allowed=False, starlink_allowed=False)
    validate_case(case)
    assert solve_exact(case) == {"status": "infeasible", "optimal_bits": [],
                                 "optimal_full_bits": [], "minimum_score": None, "evaluations": 0}
    with pytest.raises(ValueError):
        build_responsibility_qubo(case)
    with pytest.raises(ValueError):
        evaluate_assignment(case, "0")


def test_unit_fleet_control_has_all_20_tied_optima():
    case = synthetic_case()
    result = solve_exact(case, eta=0, background=False)
    expected = {"".join(bits) for bits in product("01", repeat=6) if bits.count("1") == 3}
    assert set(result["optimal_bits"]) == expected
    assert len(expected) == 20 and result["evaluations"] == 64
    assert result["minimum_score"] == 18 / 64  # W_ref remains 8 with debris off.


def test_different_partners_2_844_seconds_apart_are_distinct_events():
    case = two_shared_events()
    validate_case(case)
    assert len(free_event_ids(case)) == 2
    assert evaluate_assignment(case, "11")["satellite_burdens"]["O1"] == 4


def test_same_pair_and_tca_is_rejected_even_with_new_record_id():
    case = two_shared_events()
    duplicate = dict(case["events"][0], event_id="another-id",
                     tca=case["events"][0]["tca"].replace("Z", "+00:00"))
    case["events"].append(duplicate)
    case["W_ref"] += 1
    with pytest.raises(ValueError, match="pair plus TCA"):
        validate_case(case)


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf, 0, -1, True, "1"])
def test_nonfinite_or_invalid_weights_are_rejected(bad):
    case = two_shared_events()
    case["events"][0]["weight"] = bad
    with pytest.raises((TypeError, ValueError)):
        validate_case(case)


@pytest.mark.parametrize("bad", [np.nan, np.inf, 0, -1, True, "4", 3.9])
def test_invalid_or_understated_reference_is_rejected(bad):
    case = two_shared_events()
    case["W_ref"] = bad
    with pytest.raises((TypeError, ValueError)):
        validate_case(case)


@pytest.mark.parametrize("bad", [np.nan, np.inf, -.1, 1.1, True, "0.5"])
def test_invalid_eta_is_rejected(bad):
    with pytest.raises((TypeError, ValueError)):
        evaluate_assignment(two_shared_events(), "01", eta=bad)


def test_timestamps_missing_fields_and_false_catalog_evidence_are_rejected():
    case = two_shared_events()
    case["events"][0]["tca"] = "2026-11-15T01:00:00"
    with pytest.raises(ValueError, match="UTC"):
        validate_case(case)
    case = two_shared_events()
    del case["events"][0]["oneweb_allowed"]
    with pytest.raises(KeyError):
        validate_case(case)
    case = two_shared_events()
    case["background"][0]["catalog_confirmed"] = False
    with pytest.raises(ValueError, match="confirmed"):
        validate_case(case)


def test_background_must_be_time_aligned_and_a_selected_satellite():
    case = two_shared_events()
    case["background"][0]["tca"] = "2026-11-16T01:30:00Z"
    with pytest.raises(ValueError, match="horizon"):
        validate_case(case)
    case = two_shared_events()
    case["background"][0]["satellite_id"] = "not-selected"
    with pytest.raises(ValueError, match="selected"):
        validate_case(case)


def test_background_requires_debris_identity_and_deduplicates_pair_tca():
    case = two_shared_events()
    del case["background"][0]["debris_id"]
    with pytest.raises(KeyError):
        validate_case(case)
    case = two_shared_events()
    duplicate = dict(case["background"][0], event_id="another-background-id")
    case["background"].append(duplicate)
    case["W_ref"] += duplicate["weight"]
    with pytest.raises(ValueError, match="background satellite pair"):
        validate_case(case)


def test_empty_case_has_zero_flat_deterministic_objective():
    case = synthetic_case()
    case.update(events=[], background=[], W_ref=1)
    assert solve_exact(case)["minimum_score"] == 0
    assert evaluate_assignment(case, "")["objective_score"] == 0
