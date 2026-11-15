"""Read-only, new-model fixed-angle hardware proposal. There is no submission path."""

import argparse
from datetime import datetime, timezone
import json
import logging
import math
import os
from pathlib import Path
import warnings

from qiskit import QuantumCircuit, qpy, transpile
from quantum import build_qaoa_circuit, qubo_to_ising
from research.responsibility import build_responsibility_qubo
from research.socrates_gate import adapt_case


def verify_layout(circuit):
    if circuit.num_clbits != 6 or len(circuit.cregs) != 1:
        raise ValueError("expected six canonical classical bits in one register")
    physical = (circuit.layout.final_index_layout(filter_ancillas=True)
                if circuit.layout else list(range(6)))
    if len(physical) != 6 or len(set(physical)) != 6:
        raise ValueError("invalid logical-to-physical layout")
    measured, mapping = set(), {}
    for instruction in circuit.data:
        qubits = [circuit.find_bit(q).index for q in instruction.qubits]
        if instruction.operation.name == "measure":
            bit = circuit.find_bit(instruction.clbits[0]).index
            if bit in mapping or qubits[0] in measured:
                raise ValueError("repeated measurement")
            mapping[bit] = qubits[0]
            measured.add(qubits[0])
        elif instruction.operation.name != "barrier" and any(q in measured for q in qubits):
            raise ValueError("operation after measurement on a measured qubit")
    if mapping != dict(enumerate(physical)):
        raise ValueError("measurement wiring does not match logical event order")
    return physical


def choose_training_record(runs):
    records = [json.loads(path.read_text()) for path in Path(runs).glob("priority-debris-on-*-qaoa_p1.json")]
    if sorted(record["seed"] for record in records) != [7, 19, 43]:
        raise ValueError("require all three recorded training seeds")
    if any(record["model_id"] != "qubital.responsibility.v1" or not record["success"] for record in records):
        raise ValueError("all new-model sampling records must be available")
    return min(records, key=lambda r: (r["training_and_sampling"]["expectation"], r["seed"]))


def prepare(snapshot_root, runs, output, backend_name="ibm_fez"):
    output = Path(output)
    if output.exists():
        raise ValueError("choose a new output directory")
    present = {name: bool(os.environ.get(name)) for name in ("qiskithacks", "ibmcrn")}
    if not all(present.values()):
        raise RuntimeError("secure environment bindings unavailable; values are never logged")
    selected = choose_training_record(runs)
    case = adapt_case(snapshot_root, "priority")
    angles = selected["training_and_sampling"]["angles"]
    cost = qubo_to_ising(build_responsibility_qubo(case, eta=.5, background=True))
    circuit = build_qaoa_circuit(cost, **angles, measure=True)
    circuit.name = "responsibility_v1_priority_background_on"
    controls = []
    for i in range(6):
        control = QuantumCircuit(6, 6, name=f"event_mapping_{i}")
        control.x(i)
        control.measure(range(6), range(6))
        controls.append(control)
    previous_logging = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from qiskit_ibm_runtime import QiskitRuntimeService
            service = QiskitRuntimeService(channel="ibm_quantum_platform",
                                          token=os.environ["qiskithacks"], instance=os.environ["ibmcrn"])
            if service.active_instance() != os.environ["ibmcrn"]:
                raise RuntimeError("active instance mismatch")
            usage = service.usage()
            backend = service.backend(backend_name)
            status = backend.status()
            if not status.operational or backend.num_qubits < 6:
                raise RuntimeError("proposed processor is not currently eligible")
            compiled = transpile(circuit, backend, seed_transpiler=7, optimization_level=1)
            physical = verify_layout(compiled)
            compiled_controls = transpile(controls, backend, initial_layout=physical,
                                          seed_transpiler=7, optimization_level=1)
            for control in compiled_controls:
                if verify_layout(control) != physical:
                    raise ValueError("controls must use the QAOA physical qubits")
            processors = []
            for b in service.backends(simulator=False):
                current = b.status()
                processors.append({"name": b.name, "qubits": b.num_qubits,
                                   "operational": current.operational, "pending_jobs": current.pending_jobs})
            jobs = service.jobs(limit=20, instance=os.environ["ibmcrn"], descending=True)
            job_ids = [job.job_id() for job in jobs]
            rep_delay = backend.configuration().default_rep_delay
            isa = [compiled, *compiled_controls]
            details = []
            for c, shots in zip(isa, [4096, *([32] * 6)]):
                details.append({"name": c.name, "shots": shots, "logical_qubits": 6,
                                "physical_event_qubits": verify_layout(c), "depth": c.depth(),
                                "two_qubit_gates": sum(len(i.qubits) == 2 for i in c.data),
                                "operations": dict(c.count_ops()),
                                "estimated_duration_seconds": c.estimate_duration(backend.target, unit="s")})
            seconds = math.fsum(row["shots"] * (row["estimated_duration_seconds"] + rep_delay) for row in details)
            allowed = ("usage_consumed_ru", "usage_limit_ru", "usage_allocation_ru", "usage_remaining_seconds", "usage_period")
            report = {
                "model_id": case["model_id"], "schema_version": "1.0", "weight_variant": "priority",
                "eta": .5, "background": True, "W_ref": case["W_ref"],
                "data_sha256": case["source_sha256"],
                "checked_at_utc": datetime.now(timezone.utc).isoformat(),
                "execution_type": "proposal_only_local_transpilation", "hardware_jobs_submitted": 0,
                "submission_authorized": False, "environment_variables_present": present,
                "requested_instance_matches": True, "backend": backend.name,
                "backend_pending_jobs": status.pending_jobs, "available_processors": processors,
                "accessible_job_ids_returned": job_ids, "job_history_query_limit": 20,
                "usage": {key: usage[key] for key in allowed if key in usage},
                "seed_selection_rule": "lowest actual ideal quantum expectation among all three new-model training seeds",
                "selected_training_seed": selected["seed"], "angles": angles,
                "optimizer_converged": selected["optimizer_converged"],
                "training_status": selected["training_status"],
                "sampling_plan": "fixed-angle sampling, not hardware training",
                "shots": 4288, "main_circuit_shots": 4096,
                "paired_ideal_reference": "priority-debris-on-7-qaoa_p1.json",
                "circuits": details, "default_rep_delay_seconds": rep_delay,
                "twirling": False, "mitigation": False, "dynamical_decoupling": False,
                "one_subjob_duration_model_ru": (seconds + 2) / 60,
                "one_subjob_quick_heuristic_ru": (2 + 4288 * .00035) / 60,
                "seven_subjob_quick_heuristic_ru": (14 + 4288 * .00035) / 60,
                "estimate_caveat": "planning scenarios, not guaranteed bounds or billing quote",
            }
    except Exception as error:
        raise RuntimeError(f"read-only IBM proposal blocked ({type(error).__name__})") from None
    finally:
        logging.disable(previous_logging)
    output.mkdir(parents=True)
    for name, circuits in (("logical.qpy", [circuit, *controls]), ("isa.qpy", isa)):
        with (output / name).open("xb") as stream:
            qpy.dump(circuits, stream)
    (output / "proposal.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-root", required=True, type=Path)
    parser.add_argument("--runs", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = prepare(args.snapshot_root, args.runs, args.output)
        print(json.dumps({"backend": report["backend"], "shots": report["shots"],
                          "selected_training_seed": report["selected_training_seed"],
                          "one_subjob_duration_model_ru": report["one_subjob_duration_model_ru"],
                          "hardware_jobs_submitted": 0}, indent=2))
    except Exception as error:
        # SDK exception text can contain private account identifiers.
        print(json.dumps({"status": "proposal preparation failed", "error_type": type(error).__name__}))
        raise SystemExit(1)
