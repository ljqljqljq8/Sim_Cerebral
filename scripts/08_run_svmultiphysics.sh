#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CASE="$ROOT/cases/cow_luisi_mvp"
SOLVER_DIR="$CASE/solver"

DEFAULT_SV_MULTIPHYSICS_BIN="/usr/local/sv/svMultiPhysics/2025-06-06/bin/svmultiphysics"
SV_MULTIPHYSICS_BIN="${SV_MULTIPHYSICS_BIN:-$DEFAULT_SV_MULTIPHYSICS_BIN}"
MPIEXEC="${MPIEXEC:-mpiexec}"
MPI_NP="${MPI_NP:-4}"
SOLVER_XML="${SOLVER_XML:-solver.xml}"

if [[ "$SV_MULTIPHYSICS_BIN" == */* ]]; then
  if [[ ! -x "$SV_MULTIPHYSICS_BIN" ]]; then
    echo "svMultiPhysics executable not found: $SV_MULTIPHYSICS_BIN" >&2
    echo "Set SV_MULTIPHYSICS_BIN=/path/to/svmultiphysics and rerun." >&2
    exit 127
  fi
elif ! command -v "$SV_MULTIPHYSICS_BIN" >/dev/null 2>&1; then
  echo "svMultiPhysics executable not found: $SV_MULTIPHYSICS_BIN" >&2
  echo "Set SV_MULTIPHYSICS_BIN=/path/to/svmultiphysics and rerun." >&2
  exit 127
fi

if ! command -v "$MPIEXEC" >/dev/null 2>&1; then
  echo "MPI executable not found: $MPIEXEC" >&2
  echo "Set MPIEXEC=/path/to/mpiexec and rerun." >&2
  exit 127
fi

cd "$SOLVER_DIR"
if [[ ! -f "$SOLVER_XML" ]]; then
  echo "Solver XML not found: $SOLVER_DIR/$SOLVER_XML" >&2
  exit 66
fi

"$MPIEXEC" -np "$MPI_NP" "$SV_MULTIPHYSICS_BIN" "$SOLVER_XML" | tee "${SOLVER_XML%.xml}.run.log"
