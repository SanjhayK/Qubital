"""Prepare Qubital circuits and optionally read IBM access/usage; never submit jobs.

Default is entirely offline. --check-ibm uses only service initialization, instance,
usage, backend status, and local transpilation. No job or primitive is constructed.
Credentials are read from the named variables and are never saved or displayed.
"""

import argparse
import json
import logging
from math import isfinite
import os
from pathlib import Path
import sys
import warnings

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from qiskit import QuantumCircuit, qpy, transpile
from quantum import build_qaoa_circuit, build_qubo, qubo_to_ising
from scoring import load_scenario


def circuits_and_plan():
    saved = json.loads((ROOT / "results/initial-p1-original-seed7-20261114/run-classical.json").read_text())
    scenario = load_scenario(ROOT / "data/original.json")
    cost = qubo_to_ising(build_qubo(scenario, saved["alpha"]))
    qaoa = build_qaoa_circuit(cost, **saved["angles"], measure=True)
    qaoa.name = "qubital_p1_alpha025"
    circuits, shots = [qaoa], [1024]
    for i, action in enumerate(scenario["action_order"]):
        control = QuantumCircuit(6, 6, name=f"mapping_{action}")
        control.x(i)
        control.measure(range(6), range(6))
        circuits.append(control)
        shots.append(32)
    executions = sum(shots)
    return circuits, {
        "project": "Qubital", "submission_authorized": False, "jobs_submitted": 0,
        "api_key_environment_name": "qiskithacks", "instance_environment_name": "ibmcrn",
        "alpha": saved["alpha"], "angles": saved["angles"], "layers": 1,
        "backend": None, "backend_status": "pending authenticated instance access",
        "circuits": [{"name": c.name, "logical_qubits": c.num_qubits,
                      "classical_bits": c.num_clbits, "shots": n,
                      "logical_depth": c.depth(), "logical_operations": dict(c.count_ops())}
                     for c, n in zip(circuits, shots)],
        "total_circuits": len(circuits), "total_shots": executions,
        "runtime_plan": {"primitive": "SamplerV2, job mode after separate authorization",
                         "twirling": False, "dynamical_decoupling": False,
                         "error_mitigation": False, "on_hardware_angle_optimization": False},
        "usage_estimate": {
            "method": "IBM quick heuristic: 2 seconds/subjob + 350 microseconds/execution",
            "one_subjob_qpu_seconds": 2 + executions * 0.00035,
            "seven_subjobs_qpu_seconds": 14 + executions * 0.00035,
            "one_subjob_standard_qpu_ru": (2 + executions * 0.00035) / 60,
            "seven_subjobs_standard_qpu_ru": (14 + executions * 0.00035) / 60,
            "status": "planning heuristic; live backend timing and actual subjob count unknown",
            "standard_qpu_seconds_per_ru": 60,
        },
        "allocation": {"reported_by_user_ru": 10, "verified_from_ibm": False},
    }


def hardware_layout(circuit, logical_width=6):
    """Verify logical i -> physical final_layout[i] -> canonical classical bit i.

    The independent core decoder intentionally accepts only identity layouts.
    Hardware ISA circuits may include unused physical qubits; verify explicitly.
    """
    if (circuit.num_clbits != logical_width or len(circuit.cregs) != 1
            or len(circuit.cregs[0]) != logical_width):
        raise ValueError("hardware proposal requires one canonical classical register")
    physical = (circuit.layout.final_index_layout(filter_ancillas=True)
                if circuit.layout is not None else list(range(logical_width)))
    if len(physical) != logical_width or len(set(physical)) != logical_width:
        raise ValueError("unexpected logical-to-physical layout")
    mapping = {}
    measured = False
    for instruction in circuit.data:
        if instruction.operation.name == "measure":
            measured = True
            q = circuit.find_bit(instruction.qubits[0]).index
            c = circuit.find_bit(instruction.clbits[0]).index
            if c in mapping:
                raise ValueError("classical bit measured more than once")
            mapping[c] = q
        elif measured and instruction.operation.name != "barrier":
            raise ValueError("measurements must be final")
    if mapping != dict(enumerate(physical)):
        raise ValueError("hardware measurement wiring does not match logical action order")
    return physical


def ibm_probe(circuits, key_name):
    present = {name: bool(os.environ.get(name)) for name in (key_name, "ibmcrn")}
    report = {"environment_variables_present": present, "jobs_submitted": 0}
    if not all(present.values()):
        return report | {"status": "blocked: required runtime variables are unavailable"}
    # Suppress SDK diagnostics that could include credentials or the instance CRN.
    previous_disable = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    stage = "SDK import"
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from qiskit_ibm_runtime import QiskitRuntimeService
        stage = "authentication and instance selection"
        service = QiskitRuntimeService(channel="ibm_quantum_platform",
                                      token=os.environ[key_name], instance=os.environ["ibmcrn"])
        matches = service.active_instance() == os.environ["ibmcrn"]
        report["requested_instance_matches"] = matches
        if not matches:
            return report | {"status": "blocked: active instance mismatch"}
        stage = "instance allocation read"
        usage = service.usage()
        allowed = ("usage_consumed_ru", "usage_limit_ru", "usage_allocation_ru",
                   "usage_consumed_seconds", "usage_limit_seconds", "usage_allocation_seconds",
                   "usage_remaining_seconds", "usage_period", "usage_limit_reached")
        report["allocation"] = {k: usage[k] for k in allowed if k in usage}
        consumed, limit = usage.get("usage_consumed_ru"), usage.get("usage_limit_ru")
        if (isinstance(consumed, (int, float)) and isinstance(limit, (int, float))
                and isfinite(consumed) and isfinite(limit)):
            report["allocation"]["derived_remaining_ru_to_usage_limit"] = max(0, limit - consumed)
        stage = "processor access read"
        backends = service.backends(simulator=False, min_num_qubits=6)
        processors = []
        for backend in backends:
            status = backend.status()
            processors.append({"name": backend.name, "qubits": backend.num_qubits,
                               "operational": status.operational, "pending_jobs": status.pending_jobs})
        report["available_processors"] = sorted(processors, key=lambda b: b["name"])
        eligible = [b for b in processors if b["operational"]]
        if eligible:
            choice = min(eligible, key=lambda b: (b["pending_jobs"], b["name"]))
            backend = next(b for b in backends if b.name == choice["name"])
            stage = "local hardware transpilation"
            compiled = transpile(circuits, backend, optimization_level=1, seed_transpiler=7)
            report["proposed_backend"] = choice["name"]
            report["selection_reason"] = "operational, at least six qubits, lowest pending-job count"
            report["compiled_circuits"] = []
            for c in compiled:
                detail = {"name": c.name, "physical_action_qubits": hardware_layout(c),
                          "depth": c.depth(), "operations": dict(c.count_ops())}
                try:
                    detail["estimated_circuit_duration_seconds"] = c.estimate_duration(backend.target, unit="s")
                except Exception:
                    detail["estimated_circuit_duration_seconds"] = None
                report["compiled_circuits"].append(detail)
        report["status"] = "authenticated instance access verified; no job submitted"
        return report
    except Exception as error:
        # Do not print exception messages, traceback, account dicts, or CRNs.
        return report | {"status": "blocked", "stage": stage, "error_type": type(error).__name__}
    finally:
        logging.disable(previous_disable)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="new directory; existing files preserved")
    parser.add_argument("--check-ibm", action="store_true", help="read-only authentication/instance/backend checks")
    parser.add_argument("--api-key-env", default="qiskithacks", choices=("qiskithacks", "quiskithacks"))
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error("choose a new output directory")
    circuits, plan = circuits_and_plan()
    plan["api_key_environment_name"] = args.api_key_env
    if args.check_ibm:
        plan["ibm_access"] = ibm_probe(circuits, args.api_key_env)
        if plan["ibm_access"].get("proposed_backend"):
            plan["backend"] = plan["ibm_access"]["proposed_backend"]
            plan["backend_status"] = "proposed only; not submitted"
    args.output_dir.mkdir(parents=True)
    with (args.output_dir / "circuits.qpy").open("wb") as output:
        qpy.dump(circuits, output)
    (args.output_dir / "proposal.json").write_text(json.dumps(plan, indent=2, allow_nan=False) + "\n")
    print(json.dumps(plan, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
