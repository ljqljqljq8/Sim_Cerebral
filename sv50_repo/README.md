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
- `configs/bc_visible_sta_baseline.yaml`: explicit copy of the default visible-STA baseline.
- `docs/visible_sta_baseline_bc.md`: baseline BC interpretation and limitations.
- `scripts/auto_solve.py`: one-command prepare, BC, XML, restart XML, launch scripts, and solver dry-run/run/resume.

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
- `case/sv50/simulation_truth/solver_resume.xml`
- `case/sv50/simulation_truth/run.sh`
- `case/sv50/simulation_truth/resume.sh`

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
python scripts/auto_solve.py --run --np 8 --cycles 2 --save-increment 20 --restart-increment 50
```

Production-like:

```bash
cd sv50_repo
python scripts/auto_solve.py --run --np 8 --production
```

## Restart / Resume

The sv50 launcher is aligned with the CoW restart pattern:

- initial run uses `solver.xml`
- resume run uses `solver_resume.xml`
- restart state is expected under `case/sv50/simulation_truth/<MPI_NP>-procs/stFile_last.bin`
- resume should use the same `--np` / `MPI_NP` as the original run

Recommended production cadence:

```bash
cd sv50_repo
python scripts/auto_solve.py --run --np 8 --cycles 3 --save-increment 20 --restart-increment 50
```

Resume after interruption:

```bash
cd sv50_repo
python scripts/auto_solve.py --resume --run --np 8 --cycles 3 --save-increment 20 --restart-increment 50
```

Equivalent CoW-style shell launchers are generated in `case/sv50/simulation_truth`:

```bash
cd case/sv50/simulation_truth
MPI_NP=8 bash run.sh
MPI_NP=8 bash resume.sh
```

## Current BC Assumption

The default `configs/bc.yaml` is the visible-STA baseline from the recommended
BC package. It uses 710 ml/min total inflow:

- left/right CCA: 270 ml/min each
- left/right VA: 85 ml/min each

Outlets are assigned target mean flows summing to 710 ml/min:

- brain outlets: 670 ml/min total
- explicit visible STA/TFA outlets: 40 ml/min total

This baseline does not add hidden ECA bed outlets. Therefore `L_CCA_IN` and
`R_CCA_IN` should be interpreted as ICA/CoW inflow plus the currently explicit
STA/TFA branch loss, not as full physiologic CCA inflow including maxillary,
facial, occipital, lingual, and other omitted ECA beds.

The RCR table is generated from these target flows, a mean pressure target of
90 mmHg, distal pressure of 10 mmHg, proximal resistance fraction of 0.05, and
total compliance of `1.9e-5 cm3/barye`.

## Solver Stability Preset

The XML writer uses the same conservative startup style as the CoW automation
case:

- nonlinear iterations: `Min_iterations=2`, `Max_iterations=3`
- nonlinear tolerance: `1e-3`
- blood viscosity: `0.04 Poise`
- linear solver limits: `Max_iterations=30`, `NS_GM=25`, `NS_CG=800`
- RCR initial pressure: `87 mmHg` (`115990.14 dyn/cm2`)

These are intentionally solver-stability settings. They do not change the sv50
geometry or visible-STA baseline flow split.
