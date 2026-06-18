#!/usr/bin/env bash
set -euo pipefail

SV_MULTIPHYSICS_BIN="${SV_MULTIPHYSICS_BIN:-svmultiphysics}"
MPIEXEC="${MPIEXEC:-mpiexec}"
MPI_NP="${MPI_NP:-8}"
SOLVER_XML="${SOLVER_XML:-solver.xml}"
MPI_EXTRA_ARGS="${MPI_EXTRA_ARGS:-}"

if [[ "$MPI_NP" -gt 1 ]]; then
  # shellcheck disable=SC2086
  "$MPIEXEC" $MPI_EXTRA_ARGS -np "$MPI_NP" "$SV_MULTIPHYSICS_BIN" "$SOLVER_XML" > "${SOLVER_XML%.xml}.run.log" 2>&1
else
  "$SV_MULTIPHYSICS_BIN" "$SOLVER_XML" > "${SOLVER_XML%.xml}.run.log" 2>&1
fi
