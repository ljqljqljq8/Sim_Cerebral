#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os

from common import REPO_ROOT, load_yaml, resolve, write_json


RUN_SH = """#!/usr/bin/env bash
set -euo pipefail

SV_MULTIPHYSICS_BIN="${SV_MULTIPHYSICS_BIN:-svmultiphysics}"
MPIEXEC="${MPIEXEC:-mpiexec}"
MPI_NP="${MPI_NP:-__MPI_NP__}"
SOLVER_XML="${SOLVER_XML:-solver.xml}"
MPI_EXTRA_ARGS="${MPI_EXTRA_ARGS:-}"

if [[ "$MPI_NP" -gt 1 ]]; then
  # shellcheck disable=SC2086
  "$MPIEXEC" $MPI_EXTRA_ARGS -np "$MPI_NP" "$SV_MULTIPHYSICS_BIN" "$SOLVER_XML" > "${SOLVER_XML%.xml}.run.log" 2>&1
else
  "$SV_MULTIPHYSICS_BIN" "$SOLVER_XML" > "${SOLVER_XML%.xml}.run.log" 2>&1
fi
"""


RESUME_SH = """#!/usr/bin/env bash
set -euo pipefail

MPI_NP="${MPI_NP:-__MPI_NP__}"
RESTART_DIR="${MPI_NP}-procs"
if [[ ! -f "${RESTART_DIR}/stFile_last.bin" ]]; then
  echo "Missing restart state: ${RESTART_DIR}/stFile_last.bin" >&2
  echo "Resume must use the same MPI_NP as the original run." >&2
  exit 3
fi

SOLVER_XML=solver_resume.xml bash run.sh
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Write CoW-style run.sh/resume.sh launchers for sv50.")
    parser.add_argument("--case-dir", default="case/sv50")
    parser.add_argument("--config", default="configs/case.yaml")
    parser.add_argument("--np", type=int)
    args = parser.parse_args()

    case_dir = resolve(args.case_dir)
    sim_dir = case_dir / "simulation_truth"
    config = load_yaml(args.config)
    default_np = int(args.np if args.np is not None else config.get("solver", {}).get("mpi_np_default", 8))

    run_sh = sim_dir / "run.sh"
    resume_sh = sim_dir / "resume.sh"
    sim_dir.mkdir(parents=True, exist_ok=True)
    run_sh.write_text(RUN_SH.replace("__MPI_NP__", str(default_np)), encoding="utf-8")
    resume_sh.write_text(RESUME_SH.replace("__MPI_NP__", str(default_np)), encoding="utf-8")
    os.chmod(run_sh, 0o755)
    os.chmod(resume_sh, 0o755)
    rel_sim_dir = str(sim_dir.resolve().relative_to(REPO_ROOT))
    rel_run_sh = str(run_sh.resolve().relative_to(REPO_ROOT))
    rel_resume_sh = str(resume_sh.resolve().relative_to(REPO_ROOT))
    write_json(
        sim_dir / "run_scripts.json",
        {
            "run_sh": rel_run_sh,
            "resume_sh": rel_resume_sh,
            "default_mpi_np": default_np,
            "run_command": f"cd {rel_sim_dir} && MPI_NP={default_np} bash run.sh",
            "resume_command": f"cd {rel_sim_dir} && MPI_NP={default_np} bash resume.sh",
        },
    )
    print(f"wrote {run_sh}")
    print(f"wrote {resume_sh}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
