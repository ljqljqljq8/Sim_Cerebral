#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from common import REPO_ROOT, run, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="One-command sv50 prepare, BC, XML, and solver dry-run/run.")
    parser.add_argument("--run", action="store_true", help="Launch svMultiPhysics. Default only performs dry-run.")
    parser.add_argument("--np", type=int, default=1)
    parser.add_argument("--n-steps", type=int, default=20)
    parser.add_argument("--cycles", type=float)
    parser.add_argument("--save-increment", type=int, default=20)
    parser.add_argument("--restart-increment", type=int)
    parser.add_argument("--resume", action="store_true", help="Run solver_resume.xml from an existing stFile_last.bin.")
    parser.add_argument("--allow-missing-restart", action="store_true")
    parser.add_argument("--production", action="store_true")
    parser.add_argument("--timeout-s", type=float)
    args = parser.parse_args()

    steps: list[list[str]] = [
        [sys.executable, "scripts/prepare_case.py"],
        [sys.executable, "scripts/make_bc.py"],
    ]
    xml_base = [
        sys.executable,
        "scripts/write_solver_xml.py",
        "--save-increment",
        str(args.save_increment),
    ]
    if args.restart_increment is not None:
        xml_base += ["--restart-increment", str(args.restart_increment)]
    if args.cycles is not None:
        xml_base += ["--cycles", str(args.cycles)]
    else:
        xml_base += ["--n-steps", str(args.n_steps)]
    if args.production:
        xml_base.append("--production")
    steps.append([*xml_base, "--out", "simulation_truth/solver.xml"])
    steps.append([*xml_base, "--resume", "--out", "simulation_truth/solver_resume.xml"])
    steps.append([sys.executable, "scripts/write_run_scripts.py", "--np", str(args.np)])

    run_cmd = [sys.executable, "scripts/run_solver.py", "--np", str(args.np)]
    if args.resume:
        run_cmd.append("--resume")
    if args.allow_missing_restart:
        run_cmd.append("--allow-missing-restart")
    if args.run:
        run_cmd.append("--run")
        if args.timeout_s is not None:
            run_cmd += ["--timeout-s", str(args.timeout_s)]
    steps.append(run_cmd)

    completed = []
    for cmd in steps:
        rc = run(cmd, cwd=REPO_ROOT)
        completed.append({"command": cmd, "returncode": rc})
        if rc:
            write_json(
                "case/sv50/simulation_truth/auto_status.json",
                {"status": "timed_out" if rc == 124 else "failed", "completed": completed},
            )
            return rc

    status = {
        "status": "launched" if args.run else "ready_to_run",
        "completed": completed,
        "solver_xml": "case/sv50/simulation_truth/solver_resume.xml" if args.resume else "case/sv50/simulation_truth/solver.xml",
        "resume_xml": "case/sv50/simulation_truth/solver_resume.xml",
        "solver_status": "case/sv50/simulation_truth/solver_status.json",
    }
    write_json("case/sv50/simulation_truth/auto_status.json", status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
