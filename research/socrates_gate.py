"""Offline provenance gate for the frozen SOCRATES responsibility study.

No source rows are bundled or published by this module. The raw snapshot stays
in the user's private data package; only aggregate audits may be committed.
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path

SOURCE_URL = "https://celestrak.org/SOCRATES/sort-minRange.csv"
EXPECTED_SHA256 = "53f6fa639083579e65921cd3058ec2370f537eecb05d77398ec9d0989e22edec"
EXPECTED_BYTES = 22493166
EXPECTED_ROWS = 198115
KNOWN_AVAILABLE = datetime.fromisoformat("2026-11-14T21:40:05.826487+00:00")
LEAD_HOURS = 6
NUMERIC = ("DSE_1", "DSE_2", "TCA_RANGE", "TCA_RELATIVE_SPEED", "MAX_PROB", "DILUTION")
REQUIRED = ("NORAD_CAT_ID_1", "OBJECT_NAME_1", "DSE_1", "NORAD_CAT_ID_2",
            "OBJECT_NAME_2", "DSE_2", "TCA", "TCA_RANGE", "TCA_RELATIVE_SPEED", "MAX_PROB", "DILUTION")
DATA_DICTIONARY = {
    "NORAD_CAT_ID_1/NORAD_CAT_ID_2": "positive integer catalog identifiers, not company identifiers",
    "OBJECT_NAME_1/OBJECT_NAME_2": "catalog names; constellation grouping uses documented name prefixes",
    "TCA": "predicted closest-approach time; source's naive timestamps are documented UTC",
    "DSE_1/DSE_2": "days: orbital-data age at TCA; not measured covariance or calibrated accuracy",
    "TCA_RANGE": "km: predicted minimum separation, not an avoidance burn",
    "TCA_RELATIVE_SPEED": "km/s: predicted relative speed",
    "MAX_PROB": "dimensionless conservative screening construction, not true event probability",
    "DILUTION": "km: screening dilution threshold, not measured orbital covariance",
}


def utc_time(value: str) -> datetime:
    """Parse source-format naive UTC or an explicitly UTC timestamp."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("missing TCA")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def event_key(row: dict) -> tuple[int, int, datetime]:
    ids = []
    for i in (1, 2):
        ident = str(row[f"NORAD_CAT_ID_{i}"])
        if not ident.isdigit() or int(ident) <= 0:
            raise ValueError("catalog identifiers must be positive integers")
        ids.append(int(ident))
    if ids[0] == ids[1]:
        raise ValueError("self-pair is not an encounter")
    return (*sorted(ids), utc_time(row["TCA"]))


def validate_row(row: dict) -> None:
    if any(field not in row or row[field] is None or not row[field].strip() for field in REQUIRED):
        raise ValueError("missing source field")
    event_key(row)
    for field in NUMERIC:
        value = float(row[field])
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"invalid finite nonnegative {field}")
    if not 0 <= float(row["MAX_PROB"]) <= 1:
        raise ValueError("MAX_PROB outside [0,1]")


def read_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if tuple(reader.fieldnames or ()) != REQUIRED:
            raise ValueError("unexpected SOCRATES columns")
        return list(reader)


def _oneweb_starlink(row):
    names = [row[f"OBJECT_NAME_{i}"].upper() for i in (1, 2)]
    return (any(name.startswith("ONEWEB-") for name in names)
            and any(name.startswith("STARLINK-") for name in names))


def _sort_key(row):
    return (utc_time(row["TCA"]), int(row["NORAD_CAT_ID_1"]), int(row["NORAD_CAT_ID_2"]))


def _snapshot(snapshot_root: str | Path):
    """Cache parsing by current file contents, never by an unverified path alone."""
    root = Path(snapshot_root).resolve()
    manifest_bytes = (root / "DATA_MANIFEST.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    fingerprint = [("DATA_MANIFEST.json", hashlib.sha256(manifest_bytes).hexdigest())]
    names = {entry["file"] for entry in manifest["files"]} | {"SOCRATES-sort-minRange.csv"}
    for name in sorted(names):
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("unsafe manifest path")
        fingerprint.append((name, hashlib.sha256((root / relative).read_bytes()).hexdigest()))
    return _validated_snapshot(str(root), tuple(fingerprint))


@lru_cache(maxsize=2)
def _validated_snapshot(snapshot_root: str, _content_fingerprint: tuple):
    root = Path(snapshot_root)
    manifest = json.loads((root / "DATA_MANIFEST.json").read_text())
    for entry in manifest["files"]:
        relative = Path(entry["file"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("unsafe manifest path")
        data = (root / relative).read_bytes()
        if len(data) != entry["bytes"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError(f"manifest integrity failed: {relative}")
    raw_path = root / "SOCRATES-sort-minRange.csv"
    raw_bytes = raw_path.read_bytes()
    if len(raw_bytes) != EXPECTED_BYTES or hashlib.sha256(raw_bytes).hexdigest() != EXPECTED_SHA256:
        raise ValueError("frozen source bytes/hash mismatch")
    source = json.loads((root / "SOCRATES-source.json").read_text())
    if source["url"] != SOURCE_URL or utc_time(source["downloaded_at_utc"]) != KNOWN_AVAILABLE:
        raise ValueError("known-available source provenance mismatch")
    rows = read_rows(raw_path)
    if len(rows) != EXPECTED_ROWS:
        raise ValueError("frozen row count mismatch")
    keys = set()
    for row in rows:
        validate_row(row)
        key = event_key(row)
        if key in keys:
            raise ValueError("canonical pair-plus-TCA duplicate")
        keys.add(key)
    cross = [row for row in rows if _oneweb_starlink(row)]
    cutoff = KNOWN_AVAILABLE + timedelta(hours=LEAD_HOURS)
    eligible = sorted((row for row in cross if utc_time(row["TCA"]) >= cutoff), key=_sort_key)
    primary = eligible[:6]
    if len(cross) != 17 or len(eligible) != 10 or len(primary) != 6:
        raise ValueError("frozen selection denominators changed")
    for expected, actual in (("oneweb-starlink-all17.csv", cross),
                             ("oneweb-starlink-future6h-10.csv", eligible),
                             ("primary6-earliest-eligible-events.csv", primary)):
        if read_rows(root / expected) != actual:
            raise ValueError(f"derived slice mismatch: {expected}")
    active = {row[f"NORAD_CAT_ID_{i}"]: ("OneWeb" if row[f"OBJECT_NAME_{i}"].upper().startswith("ONEWEB-") else "Starlink")
              for row in primary for i in (1, 2)}
    end = utc_time(primary[-1]["TCA"])
    candidates = []
    all_oneweb = []
    for row in rows:
        time = utc_time(row["TCA"])
        if time < cutoff:
            continue
        for i, j in ((1, 2), (2, 1)):
            ident = row[f"NORAD_CAT_ID_{i}"]
            name = row[f"OBJECT_NAME_{j}"].upper()
            if ident in active and (" DEB" in name or " R/B" in name):
                if active[ident] == "OneWeb":
                    all_oneweb.append((row, i, j))
                if time <= end:
                    candidates.append((row, i, j))
                break
    candidates.sort(key=lambda item: _sort_key(item[0]))
    for expected in ("primary6-aligned-debris-background.csv", "primary6-symmetric-debris-candidates.csv"):
        if [row for row, _, _ in candidates] != read_rows(root / expected):
            raise ValueError("aligned symmetric background did not reproduce")
    if len(candidates) != 2 or len(all_oneweb) != 5:
        raise ValueError("debris discovery denominators changed")
    verified = set()
    for row, _, j in all_oneweb:
        ident = row[f"NORAD_CAT_ID_{j}"]
        catalog = json.loads((root / f"satcat-{ident}.json").read_text())
        if (len(catalog) != 1 or str(catalog[0]["NORAD_CAT_ID"]) != ident
                or catalog[0]["OBJECT_TYPE"] != "DEB"):
            raise ValueError("catalog type join failed")
        verified.add(ident)
    owner_codes = set()
    for ident, group in active.items():
        catalog_path = root / f"satcat-{ident}.json"
        if group == "OneWeb" and catalog_path.is_file():
            catalog = json.loads(catalog_path.read_text())
            if len(catalog) != 1 or str(catalog[0]["NORAD_CAT_ID"]) != ident:
                raise ValueError("active catalog ID join failed")
            if catalog[0]["OWNER"] != "UK":
                raise ValueError("frozen OneWeb OWNER-country check changed")
            owner_codes.add(catalog[0]["OWNER"])
    gaps = [abs((utc_time(a["TCA"]) - utc_time(b["TCA"])).total_seconds())
            for i, a in enumerate(primary) for b in primary[i + 1:]
            if set(event_key(a)[:2]) & set(event_key(b)[:2])]
    if not math.isclose(min(gaps), 2.844, abs_tol=1e-12):
        raise ValueError("close-pair dependence warning changed")
    catalog_sources = []
    for item in manifest["files"]:
        if item["file"].startswith("satcat-") and item["file"].endswith("-source.json"):
            metadata = json.loads((root / item["file"]).read_text())
            catalog_sources.append({"metadata_file": item["file"], "url": metadata["url"],
                                    "retrieved_at_utc": metadata.get("downloaded_at_utc", metadata.get("retrieved_at_utc", metadata.get("fetched_at_utc"))),
                                    "completion_timestamp_not_logged": bool(metadata.get("download_completion_timestamp_not_explicitly_logged", False))})
    audit = {
        "gate": "pass_with_stated_model_and_source_limitations", "source_url": SOURCE_URL,
        "raw_sha256": EXPECTED_SHA256, "raw_bytes": len(raw_bytes), "raw_rows": len(rows),
        "data_manifest_sha256": hashlib.sha256((root / "DATA_MANIFEST.json").read_bytes()).hexdigest(),
        "verified_file_digests": [{"file": item["file"], "bytes": item["bytes"], "sha256": item["sha256"]}
                                  for item in manifest["files"]],
        "known_available_cutoff_utc": KNOWN_AVAILABLE.isoformat(), "modeled_lead_hours": LEAD_HOURS,
        "eligible_from_utc": cutoff.isoformat(), "case_end_utc": end.isoformat(),
        "cross_fleet_rows": len(cross), "excluded_already_past": sum(utc_time(r["TCA"]) < KNOWN_AVAILABLE for r in cross),
        "excluded_future_under_six_hours": sum(KNOWN_AVAILABLE <= utc_time(r["TCA"]) < cutoff for r in cross),
        "eligible_rows": len(eligible), "primary_rows": len(primary), "participating_satellites": len(active),
        "canonical_pair_tca_duplicates": 0, "missing_or_nonfinite_numeric_cells": 0,
        "verified_debris_candidates_in_full_future_snapshot": len(all_oneweb),
        "aligned_background_rows": len(candidates), "aligned_background_by_group": {
            group: sum(active[row[f"NORAD_CAT_ID_{i}"]] == group for row, i, _ in candidates)
            for group in ("OneWeb", "Starlink")},
        "satcat_verified_debris_types": len(verified), "nearest_shared_satellite_gap_seconds": min(gaps),
        "selected_oneweb_satcat_owner_codes": sorted(owner_codes),
        "catalog_source_metadata": catalog_sources,
        "catalog_classification_available_at_raw_cutoff_established": False,
        "close_pair_is_duplicate": False, "data_dictionary": DATA_DICTIONARY,
        "selection_rule": "earliest six by UTC TCA then source catalog IDs after frozen known-available time plus modeled six hours; before solver outcomes",
        "classification_complete": False,
        "limitations": ["Screening predictions, not observed collisions or validated burns",
                        "Debris discovered by DEB/R/B name candidates then catalog confirmation; not exhaustive threat classification",
                        "No matched Starlink debris in this snapshot/window is not evidence of zero fleet-wide burden",
                        "Event independence omits trajectory changes and coupled maneuvers",
                        "Source owner country is not maneuvering company; active status does not prove response capability",
                        "SATCAT was retrieved after raw-screen cutoff; type checks are later research validation, not proven operational knowledge at the cutoff",
                        "No redistribution license inferred; raw/source rows remain outside Git"],
    }
    return primary, candidates, active, audit


def audit_snapshot(snapshot_root: str | Path) -> dict:
    """Return aggregate-only audit; source records and identifiers are not exported."""
    return json.loads(json.dumps(_snapshot(snapshot_root)[3]))


def adapt_case(snapshot_root: str | Path, weight_variant: str = "unit") -> dict:
    """Construct an in-memory responsibility case from private frozen source bytes.

    Background is always retained; score(background=False) toggles it while keeping
    W_ref identical. This function does not write selected source rows to disk.
    """
    if weight_variant not in ("unit", "priority"):
        raise ValueError("weight_variant must be unit or priority")
    primary, background, active, audit = _snapshot(snapshot_root)
    scale = max(float(row["MAX_PROB"]) for row in primary)
    if scale <= 0:
        raise ValueError("priority reference requires positive screening weights")
    def weight(row):
        value = 1.0 if weight_variant == "unit" else float(row["MAX_PROB"]) / scale
        if not math.isfinite(value) or value <= 0:
            raise ValueError("modeled weights must be positive finite")
        return value
    events = []
    for index, row in enumerate(primary):
        oneweb = 1 if row["OBJECT_NAME_1"].upper().startswith("ONEWEB-") else 2
        starlink = 3 - oneweb
        events.append({"event_id": f"event_{index}", "tca": utc_time(row["TCA"]).isoformat(),
                       "oneweb_id": row[f"NORAD_CAT_ID_{oneweb}"], "starlink_id": row[f"NORAD_CAT_ID_{starlink}"],
                       "weight": weight(row), "oneweb_allowed": True, "starlink_allowed": True})
    fixed = [{"event_id": f"background_{index}", "tca": utc_time(row["TCA"]).isoformat(),
              "group": active[row[f"NORAD_CAT_ID_{i}"]], "satellite_id": row[f"NORAD_CAT_ID_{i}"],
              "debris_id": row[f"NORAD_CAT_ID_{j}"],
              "weight": weight(row), "object_type": "DEB", "catalog_confirmed": True}
             for index, (row, i, j) in enumerate(background)]
    return {"model_id": "qubital.responsibility.v1", "schema_version": "1.0",
            "events": events, "background": fixed,
            "horizon_start": audit["eligible_from_utc"], "horizon_end": audit["case_end_utc"],
            "W_ref": sum(e["weight"] for e in events) + sum(b["weight"] for b in fixed),
            "weight_variant": weight_variant, "source_sha256": EXPECTED_SHA256,
            "response_capability": "assumed conditional response availability, not established by active catalog status",
            "weight_meaning": "modeled workload/priority; not fuel, delta-v, or true expected collision loss",
            "bit_meaning": "0 assigns Starlink; 1 assigns OneWeb, once per event"}
