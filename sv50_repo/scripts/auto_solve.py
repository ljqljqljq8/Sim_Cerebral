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
    parser.add_argument("--save-increment", type=int, default=10)
    parser.add_argument("--production", action="store_true")
    parser.add_argument("--timeout-s", type=float)
    args = parser.parse_args()

    steps: list[list[str]] = [
        [sys.executable, "scripts/prepare_case.py"],
        [sys.executable, "scripts/make_bc.py"],
    ]
    xml_cmd = [
        sys.executable,
        "scripts/write_solver_xml.py",
        "--save-increment",
        str(args.save_increment),
    ]
    if args.cycles is not None:
        xml_cmd += ["--cycles", str(args.cycles)]
    else:
        xml_cmd += ["--n-steps", str(args.n_steps)]
    if args.production:
        xml_cmd.append("--production")
    steps.append(xml_cmd)

    run_cmd = [sys.executable, "scripts/run_solver.py", "--np", str(args.np)]
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
        "solver_xml": "case/sv50/simulation_truth/solver.xml",
        "solver_status": "case/sv50/simulation_truth/solver_status.json",
    }
    write_json("case/sv50/simulation_truth/auto_status.json", status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
