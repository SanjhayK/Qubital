"""Offline tests of IBM request shape, evidence capture and noisy-count scoring."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from qiskit import QuantumCircuit, transpile
from qiskit.providers.fake_provider import GenericBackendV2
from qiskit.primitives.containers.sampler_pub import SamplerPub

from research import hardware_run as hw


@pytest.fixture(scope="module")
def experiment():
    root = Path(__file__).resolve().parents[1]
    snapshot = Path(os.environ.get("QUBITAL_SOCRATES_DIR", "/workspace/attachments/qubital-socrates-frozen/socrates_snapshot"))
    if not (snapshot / "SOCRATES-sort-minRange.csv").is_file():
        pytest.skip("private frozen data required for hardware case validation")
    prepared = root / "results/responsibility-hardware-20261115"
    proposal, circuits, plan = hw.check(prepared, snapshot)
    return prepared, snapshot, proposal, circuits, plan


def test_prepared_pubs_have_exact_per_circuit_shots_without_network(experiment):
    _, _, _, circuits, plan = experiment
    pubs = [SamplerPub.coerce((c, None, n)) for c, n in zip(circuits, plan["shots"])]
    assert [p.shots for p in pubs] == [4096, 32, 32, 32, 32, 32, 32]
    assert sum(p.shots for p in pubs) == 4288
    assert plan["paired_ideal_reference"] == "priority-debris-on-19-qaoa_p1.json"


def test_hardware_decoder_uses_verified_classical_wiring_after_nonidentity_layout():
    circuit = QuantumCircuit(6, 6)
    circuit.measure(range(6), range(6))
    backend = GenericBackendV2(8, seed=7)
    compiled = transpile(circuit, backend, initial_layout=[7, 6, 5, 4, 3, 2])
    assert hw.canonical_counts({"000001": 32}, compiled) == {"100000": 32}
    with pytest.raises(ValueError):
        hw.canonical_counts({"0x01": 32}, compiled)
    broken = compiled.copy()
    broken.data = [i for i in broken.data if i.operation.name != "measure"]
    broken.measure([7, 6, 5, 4, 3, 2], [5, 4, 3, 2, 1, 0])
    with pytest.raises(ValueError):
        hw.canonical_counts({"000001": 32}, broken)


def test_submit_makes_one_request_with_receipt_and_rejects_repeated_output(experiment, tmp_path, monkeypatch):
    prepared, snapshot, proposal, circuits, plan = experiment
    proposal = dict(proposal, checked_at_utc=datetime.now(timezone.utc).isoformat())
    monkeypatch.setattr(hw, "check", lambda *_: (proposal, circuits, plan))
    calls = []
    backend = SimpleNamespace(status=lambda: SimpleNamespace(operational=True),
                              target=SimpleNamespace(instruction_supported=lambda **_: True))
    service = SimpleNamespace(usage=lambda: {"usage_remaining_seconds": 600}, backend=lambda _: backend)

    class OfflineSampler:
        def __init__(self, mode, options):
            assert mode is backend and options["max_execution_time"] == 60
            assert not options["twirling"]["enable_measure"]

        def run(self, pubs):
            calls.append(pubs)
            return SimpleNamespace(job_id=lambda: "offline-test-job")

    output = tmp_path / "job"
    receipt = hw.submit(prepared, snapshot, output, plan["proposal_sha256"], service=service, sampler_factory=OfflineSampler)
    assert receipt["job_id"] == "offline-test-job"
    assert json.loads((output / "job.json").read_text())["job_id"] == "offline-test-job"
    assert len(calls) == 1 and [p[2] for p in calls[0]] == plan["shots"]
    with pytest.raises(FileExistsError):
        hw.submit(prepared, snapshot, output, plan["proposal_sha256"], service=service, sampler_factory=OfflineSampler)
    assert len(calls) == 1
    with pytest.raises(ValueError, match="changed"):
        hw.submit(prepared, snapshot, tmp_path / "changed", "wrong-sha", service=service, sampler_factory=OfflineSampler)
    assert len(calls) == 1


def test_raw_noisy_samples_are_retained_without_classical_replacement(experiment):
    prepared, snapshot, *_ = experiment
    raw = [{"000000": 4096}, *({"000000": 32} for _ in range(6))]
    result = hw.analyze(prepared, snapshot, raw)
    assert result["canonical_counts"][0] == {"000000": 4096}
    assert result["hardware_metrics"]["complete_optimum_hit_probability"] == 0
    assert result["hardware_metrics"]["best_actual_sampled_bits"] == ["000000"]
    assert all(c["observed_correct_fraction"] == 0 for c in result["mapping_controls"])
    assert not result["mitigation_applied"]


def test_collect_retrieves_existing_job_without_a_submission_interface(experiment, tmp_path):
    prepared, snapshot, _, circuits, plan = experiment
    (tmp_path / "job.json").write_text(json.dumps(dict(plan, job_id="offline-existing-job")))
    raw = [{"000000": 4096}, *({"000000": 32} for _ in range(6))]
    result = [SimpleNamespace(data=SimpleNamespace(**{c.cregs[0].name: SimpleNamespace(get_counts=lambda r=r: r)}))
              for c, r in zip(circuits, raw)]
    job = SimpleNamespace(status=lambda: "DONE", result=lambda **_: result,
                          metrics=lambda: {"usage": {"quantum_seconds": 3}, "timestamps": {}})
    service = SimpleNamespace(job=lambda _: job, usage=lambda: {"usage_remaining_seconds": 597})
    actual = hw.collect(prepared, snapshot, tmp_path, service=service)
    assert actual["status"] == "DONE"
    assert json.loads((tmp_path / "raw-counts.json").read_text()) == raw
    assert (tmp_path / "analysis.json").is_file()
    assert hw.collect(prepared, snapshot, tmp_path, service=service)["status"] == "already_collected"


def test_saved_real_hardware_counts_recompute_all_metrics_and_provenance(experiment):
    prepared, snapshot, _, _, plan = experiment
    receipt = hw.read_json(prepared / "job/job.json")
    saved = hw.read_json(prepared / "job/analysis.json")
    raw = hw.read_json(prepared / "job/raw-counts.json")
    actual = hw.analyze(prepared, snapshot, raw)
    assert all(saved[key] == value for key, value in actual.items())
    assert receipt["job_id"] == saved["job_id"] == "dbsgu4habdes73fr5530"
    assert receipt["isa_sha256"] == plan["isa_sha256"]
    assert receipt["proposal_sha256"] == plan["proposal_sha256"]
    assert receipt["hardware_jobs_submitted"] == 1
    assert hw.digest(prepared / "job/runner.py.txt") == receipt["runner_sha256"]
    assert sum(raw[0].values()) == 4096
    assert sum(sum(counts.values()) for counts in raw) == 4288
    assert saved["actual_job_metrics"]["usage"]["status"] == "complete"
