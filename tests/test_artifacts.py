"""Evidence compression must not change bytes or hide corrupted provenance."""

import gzip
import hashlib
from pathlib import Path

import pytest

from research.artifacts import (digest, read_bytes, read_json, trace_paths,
                                verify_preserved, verify_source)


def test_compressed_trace_preserves_original_bytes_and_logical_identity(tmp_path):
    path = tmp_path / "unit-debris-off-7-start-0.json"
    original = b'{"expectation":0.12345678901234567,"history":[1,2,3]}\n'
    path.with_name(path.name + ".gz").write_bytes(gzip.compress(original, mtime=0))
    assert read_bytes(path) == original
    assert digest(path) == hashlib.sha256(original).hexdigest()
    assert read_json(path)["history"] == [1, 2, 3]
    assert trace_paths(tmp_path) == [path]
    path.write_bytes(original)
    assert trace_paths(tmp_path) == [path]


def test_bad_gzip_is_rejected_instead_of_treated_as_a_missing_attempt(tmp_path):
    path = tmp_path / "case-start-0.json"
    path.with_name(path.name + ".gz").write_bytes(b"not a gzip file")
    with pytest.raises(gzip.BadGzipFile):
        read_json(path)


def test_completed_source_archive_allows_live_maintenance_but_not_tampering(tmp_path):
    source, archive = tmp_path / "runner.py", tmp_path / "runner.py.txt"
    archive.write_text("original experiment\n")
    expected = digest(archive)
    source.write_text("maintained runner\n")
    verify_source(tmp_path, "runner.py", expected, archive, completed=True)
    with pytest.raises(ValueError):
        verify_source(tmp_path, "runner.py", expected, archive, completed=False)
    archive.write_text("corrupt archive\n")
    with pytest.raises(ValueError):
        verify_source(tmp_path, "runner.py", expected, archive, completed=True)


def test_live_docs_can_change_after_completion_but_scientific_data_cannot(tmp_path):
    (tmp_path / "README.md").write_text("old docs")
    evidence = tmp_path / "results" / "samples.json"
    evidence.parent.mkdir()
    evidence.write_text('{"00":4096}')
    manifest = {name: digest(tmp_path / name) for name in ("README.md", "results/samples.json")}
    (tmp_path / "README.md").write_text("updated docs")
    assert verify_preserved(tmp_path, manifest, completed=True) == 1
    with pytest.raises(ValueError):
        verify_preserved(tmp_path, manifest, completed=False)
    evidence.write_text('{"11":4096}')
    with pytest.raises(ValueError, match="scientific"):
        verify_preserved(tmp_path, manifest, completed=True)


def test_committed_compressed_traces_match_original_and_compressed_hashes():
    root = Path(__file__).resolve().parents[1]
    index = read_json(root / "results/compressed-traces.json")
    assert len(index["files"]) == 48
    for entry in index["files"]:
        assert digest(root / entry["logical_path"]) == entry["original_sha256"]
        stored = (root / entry["stored_path"]).read_bytes()
        assert hashlib.sha256(stored).hexdigest() == entry["stored_sha256"]
        assert len(stored) == entry["stored_bytes"]
        assert len(read_bytes(root / entry["logical_path"])) == entry["original_bytes"]
