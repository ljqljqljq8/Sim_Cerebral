#!/usr/bin/env bash
set -euo pipefail

MPI_NP="${MPI_NP:-8}"
RESTART_DIR="${MPI_NP}-procs"
if [[ ! -f "${RESTART_DIR}/stFile_last.bin" ]]; then
  echo "Missing restart state: ${RESTART_DIR}/stFile_last.bin" >&2
  echo "Resume must use the same MPI_NP as the original run." >&2
  exit 3
fi

SOLVER_XML=solver_resume.xml bash run.sh
