"""Data-gate tests; small synthetic rows below are validation fixtures only."""

from copy import deepcopy
from datetime import timedelta
import json
import os
from pathlib import Path
import shutil

import pytest

from research.socrates_gate import (
    EXPECTED_SHA256, KNOWN_AVAILABLE, adapt_case, audit_snapshot, event_key, utc_time, validate_row,
)


@pytest.fixture
def row():
    return {"NORAD_CAT_ID_1": "1", "OBJECT_NAME_1": "ONEWEB-TEST",
            "DSE_1": "1", "NORAD_CAT_ID_2": "2", "OBJECT_NAME_2": "STARLINK-TEST",
            "DSE_2": "2", "TCA": "2026-11-16 11:10:03.445", "TCA_RANGE": "2",
            "TCA_RELATIVE_SPEED": "10", "MAX_PROB": "0.00001", "DILUTION": "1"}


@pytest.fixture(scope="module")
def private_snapshot():
    root = Path(os.environ.get("QUBITAL_SOCRATES_DIR",
                "/workspace/attachments/qubital-socrates-frozen/socrates_snapshot"))
    if not (root / "SOCRATES-sort-minRange.csv").is_file():
        pytest.skip("private frozen SOCRATES package unavailable; no raw data is redistributed")
    return root


def test_pair_tca_key_is_order_independent_and_utc_normalized(row):
    other = deepcopy(row)
    other["NORAD_CAT_ID_1"], other["NORAD_CAT_ID_2"] = row["NORAD_CAT_ID_2"], row["NORAD_CAT_ID_1"]
    other["TCA"] = "2026-11-16T11:10:03.445Z"
    assert event_key(row) == event_key(other)


def test_three_second_different_partner_is_not_deduplicated(row):
    other = deepcopy(row)
    other["NORAD_CAT_ID_2"] = "3"
    other["TCA"] = "2026-11-16 11:10:06.289"
    assert event_key(row) != event_key(other)
    assert (utc_time(other["TCA"]) - utc_time(row["TCA"])).total_seconds() == 2.844


@pytest.mark.parametrize("field", ["DSE_1", "DSE_2", "TCA_RANGE", "TCA_RELATIVE_SPEED", "MAX_PROB", "DILUTION"])
@pytest.mark.parametrize("value", ["nan", "inf", ""])
def test_nonfinite_or_missing_numeric_cells_are_rejected(row, field, value):
    row[field] = value
    with pytest.raises(ValueError):
        validate_row(row)


@pytest.mark.parametrize("bad_id", ["1.5", "0", "-1", "abc"])
def test_invalid_catalog_ids_rejected(row, bad_id):
    row["NORAD_CAT_ID_1"] = bad_id
    with pytest.raises(ValueError):
        validate_row(row)


def test_missing_name_rejected(row):
    row["OBJECT_NAME_1"] = ""
    with pytest.raises(ValueError):
        validate_row(row)


def test_wrong_raw_bytes_cannot_pass_even_with_empty_manifest(tmp_path):
    (tmp_path / "DATA_MANIFEST.json").write_text(json.dumps({"files": []}))
    (tmp_path / "SOCRATES-sort-minRange.csv").write_bytes(b"not the supplied source")
    with pytest.raises(ValueError, match="source bytes/hash mismatch"):
        audit_snapshot(tmp_path)


def test_frozen_gate_reproduces_selection_and_background(private_snapshot):
    audit = audit_snapshot(private_snapshot)
    assert audit["raw_sha256"] == EXPECTED_SHA256
    assert audit["raw_rows"] == 198115
    assert audit["cross_fleet_rows"] == 17
    assert audit["excluded_already_past"] == 6
    assert audit["excluded_future_under_six_hours"] == 1
    assert audit["eligible_rows"] == 10
    assert audit["primary_rows"] == 6
    assert audit["participating_satellites"] == 7
    assert audit["aligned_background_by_group"] == {"OneWeb": 2, "Starlink": 0}
    assert audit["canonical_pair_tca_duplicates"] == 0
    assert audit["missing_or_nonfinite_numeric_cells"] == 0
    assert audit["nearest_shared_satellite_gap_seconds"] == pytest.approx(2.844)
    assert audit["classification_complete"] is False
    assert audit["selected_oneweb_satcat_owner_codes"] == ["UK"]


def test_cached_parsing_does_not_hide_changed_provenance_bytes(private_snapshot, tmp_path):
    copied = tmp_path / "private-copy"
    shutil.copytree(private_snapshot, copied)
    audit_snapshot(copied)
    (copied / "SOCRATES-source.json").write_text("{}")
    with pytest.raises(ValueError, match="manifest integrity failed"):
        audit_snapshot(copied)


@pytest.mark.parametrize("variant", ["unit", "priority"])
def test_adapted_case_retains_aligned_background_and_reference_bound(private_snapshot, variant):
    case = adapt_case(private_snapshot, variant)
    assert case["model_id"] == "qubital.responsibility.v1"
    assert len(case["events"]) == 6
    assert len(case["background"]) == 2
    assert len({e["oneweb_id"] for e in case["events"]}) == 1
    assert len({e["starlink_id"] for e in case["events"]}) == 6
    assert all(e["oneweb_allowed"] and e["starlink_allowed"] for e in case["events"])
    assert case["W_ref"] == pytest.approx(sum(e["weight"] for e in case["events"])
                                          + sum(b["weight"] for b in case["background"]))
    assert utc_time(case["horizon_start"]) == KNOWN_AVAILABLE + timedelta(hours=6)
    assert all(utc_time(case["horizon_start"]) <= utc_time(b["tca"]) <= utc_time(case["horizon_end"])
               and b["object_type"] == "DEB" and b["catalog_confirmed"]
               for b in case["background"])
    if variant == "unit":
        assert case["W_ref"] == 8
    else:
        assert max(e["weight"] for e in case["events"]) == 1
        assert case["W_ref"] == pytest.approx(1.9611673672143677)


def test_unknown_weight_mapping_rejected(private_snapshot):
    with pytest.raises(ValueError):
        adapt_case(private_snapshot, "fuel")
