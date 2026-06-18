# sv50 CFD Solve Repo

This directory is a self-contained solve workspace for the `sv50` candidate.
It vendors the required geometry and mesh files under `case/sv50/source` and
organizes a clean solve case under `case/sv50`.

## Contents

- `case/sv50/simvascular/mesh/mesh-complete.mesh.vtu`: TetGen volume mesh.
- `case/sv50/simvascular/mesh/mesh-complete.exterior.vtp`: exterior surface.
- `case/sv50/simvascular/mesh/mesh-surfaces/*.vtp`: short-named boundary faces.
- `case/sv50/simvascular/face_labels.json`: boundary metadata with original names.
- `case/sv50/geometry/terminal_planes.json`: terminal planes with short names.
- `case/sv50/source`: vendored copy of the source `cfd_v5/sv50` files.
- `configs/bc.yaml`: inlet flows and outlet RCR target flow split.
- `scripts/auto_solve.py`: one-command prepare, BC, XML, and solver dry-run/run.

## Boundary Names

Inlets:

- `L_CCA_IN`, `R_CCA_IN`
- `L_VA_IN`, `R_VA_IN`

Brain outlets:

- `L_ACA_OUT`, `R_ACA_OUT`
- `L_MCA_OUT`, `R_MCA_OUT`
- `L_PCA_OUT`, `R_PCA_OUT`

External/STA outlets:

- `L_TFA_OUT`, `R_TFA_OUT`
- `L_STA_OUT1`, `R_STA_OUT1`
- `L_STA_OUT2`, `R_STA_OUT2`
- `L_STA_OUT3`, `R_STA_OUT3`
- `L_STA_FB_OUT`, `R_STA_FB_OUT`

Wall:

- `WALL`

## Portable Runtime Setup

No machine-specific absolute solver path is required in the configs.
On a new machine, either make `svmultiphysics` available on `PATH`, or set:

```bash
export SV_MULTIPHYSICS_BIN=/path/to/svmultiphysics
export MPIEXEC=/path/to/mpiexec
```

## Dry Run

```bash
cd sv50_repo
python scripts/auto_solve.py
```

This prepares the case, writes:

- `case/sv50/simulation_truth/bc_summary.json`
- `case/sv50/simulation_truth/outlet_rcr.csv`
- `case/sv50/simulation_truth/solver.xml`

and checks whether the solver command can be resolved.

## Smoke Solve

```bash
cd sv50_repo
SV_MULTIPHYSICS_BIN=/path/to/svmultiphysics python scripts/auto_solve.py --run --n-steps 20 --save-increment 10 --timeout-s 600
```

For MPI:

```bash
cd sv50_repo
SV_MULTIPHYSICS_BIN=/path/to/svmultiphysics MPIEXEC=/path/to/mpiexec python scripts/auto_solve.py --run --np 8 --n-steps 20
```

## Longer Test

```bash
cd sv50_repo
python scripts/auto_solve.py --run --np 8 --cycles 2 --save-increment 100
```

Production-like:

```bash
cd sv50_repo
python scripts/auto_solve.py --run --np 8 --production
```

## Current BC Assumption

The default `configs/bc.yaml` uses 620 ml/min total inflow:

- left/right CCA: 260 ml/min each
- left/right VA: 50 ml/min each

Outlets are assigned target mean flows summing to 620 ml/min, with dominant
MCA flow, moderate ACA/PCA flow, and small external/STA branch flows. The RCR
table is generated from these target flows, a mean pressure target of 90 mmHg,
and distal pressure of 10 mmHg.
