#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

from common import find_executable, load_yaml, resolve, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Run or dry-run svMultiPhysics for sv50.")
    parser.add_argument("--case-dir", default="case/sv50")
    parser.add_argument("--config", default="configs/case.yaml")
    parser.add_argument("--solver-xml", default="simulation_truth/solver.xml")
    parser.add_argument("--np", type=int, default=1)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--timeout-s", type=float)
    args = parser.parse_args()

    case_dir = resolve(args.case_dir)
    sim_dir = case_dir / "simulation_truth"
    solver_xml = case_dir / args.solver_xml
    config = load_yaml(args.config)
    paths = config.get("paths", {})
    overrides = paths.get("environment_overrides", {})
    exe = find_executable([
        os.environ.get(overrides.get("svmultiphysics_executable", "SV_MULTIPHYSICS_BIN")),
        paths.get("svmultiphysics_executable"),
        "svmultiphysics",
    ])
    if exe is None:
        status = {"status": "blocked", "reason": "svMultiPhysics executable not found"}
        write_json(sim_dir / "solver_status.json", status)
        print(status["reason"])
        return 2

    if args.np > 1:
        mpi = find_executable([
            os.environ.get(overrides.get("mpiexec", "MPIEXEC")),
            paths.get("mpiexec"),
            "mpiexec",
            "mpirun",
        ])
        if mpi is None:
            status = {"status": "blocked", "reason": "MPI executable not found"}
            write_json(sim_dir / "solver_status.json", status)
            print(status["reason"])
            return 2
        cmd = [str(mpi), "-np", str(args.np), str(exe), solver_xml.name]
    else:
        cmd = [str(exe), solver_xml.name]

    status = {
        "status": "ready_to_run" if not args.run else "running",
        "case_dir": str(case_dir),
        "solver_xml": str(solver_xml),
        "cwd": str(sim_dir),
        "command": cmd,
        "np": args.np,
    }
    if not args.run:
        write_json(sim_dir / "solver_status.json", status)
        print("ready_to_run")
        print("+ " + " ".join(cmd))
        return 0

    run_log = sim_dir / "solver.run.log"
    print("+ " + " ".join(cmd))
    timed_out = False
    with run_log.open("w", encoding="utf-8") as log:
        log.write("+ " + " ".join(cmd) + "\n")
        log.flush()
        try:
            rc = subprocess.run(cmd, cwd=str(sim_dir), stdout=log, stderr=subprocess.STDOUT, timeout=args.timeout_s).returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            rc = 124
            log.write(f"\nTimed out after {args.timeout_s} seconds.\n")
    results = sorted(str(p) for p in sim_dir.glob("result_*.vtu"))
    status.update({
        "status": "timed_out" if timed_out else "finished" if rc == 0 else "failed",
        "returncode": rc,
        "run_log": str(run_log),
        "result_files": results,
    })
    if timed_out:
        status["reason"] = f"Timed out after {args.timeout_s} seconds"
    write_json(sim_dir / "solver_status.json", status)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
