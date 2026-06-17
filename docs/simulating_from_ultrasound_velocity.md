# Simulating From Ultrasound Velocity

The current production model can use internal carotid artery Doppler velocity
measurements as inlet boundary conditions, but svMultiPhysics needs inlet
flow rate rather than raw velocity. The conversion used here is:

```text
area_cm2 = pi * (diameter_mm * 0.1 / 2)^2
Q_cm3_s = mean_velocity_cm_s * area_cm2
Q_mL_min = Q_cm3_s * 60
```

For an inlet, `scripts/05_generate_inlet_waveforms.py` accepts either:

- `mean_flow_mL_min`
- `mean_velocity_cm_s` plus `diameter_mm` or `area_cm2`
- `mean_velocity_m_s` plus `diameter_mm` or `area_cm2`

The generated `.flow` files are written to `cases/cow_luisi_mvp/bc/`. Inlet
flow is written with negative sign because the current face normals point out
of the computational domain.

## Current Model Boundary Conditions

The formal CoW model has four inlet caps:

- `LICA`
- `RICA`
- `LVA`
- `RVA`

It has six outlet caps:

- `LACA`
- `RACA`
- `LMCA`
- `RMCA`
- `LPCA`
- `RPCA`

In the solver XML, these are assigned as:

- Inlets: `Dir`, `Unsteady`, `Impose_flux=true`, `Profile=Parabolic`,
  `Temporal_values_file_path=../bc/<inlet>.flow`
- Outlets: `Neu`, `RCR`, using `cases/cow_luisi_mvp/bc/rcr_values.csv`
- Wall: no-slip `Dir` with value `0.0`

## Running A Patient-Velocity Case

Use `config/ultrasound_velocity_example.yaml` as the template. Replace each
`mean_velocity_cm_s` and `diameter_mm` with patient-specific values. Then run:

```bash
.venv-sv/bin/python scripts/05_generate_inlet_waveforms.py \
  --config config/ultrasound_velocity_example.yaml

.venv-sv/bin/python scripts/06_generate_rcr_table.py

.venv-sv/bin/python scripts/07_write_svmultiphysics_xml.py \
  --strict-inputs \
  --output solver_patient_ultrasound.xml \
  --mesh-subdir mesh \
  --save-every 20 \
  --fluid-max-iterations 12 \
  --ls-max-iterations 30 \
  --ns-gm-max-iterations 25 \
  --ns-cg-max-iterations 800 \
  --ls-tolerance 1e-4 \
  --krylov-dimension 300

MPI_NP=6 SOLVER_XML=solver_patient_ultrasound.xml \
  bash scripts/08_run_svmultiphysics.sh
```

After the run finishes, process the boundary and field outputs:

```bash
.venv-sv/bin/python scripts/09_postprocess_results.py
```

## What The Simulation Can And Cannot Infer

With ICA inlet velocity and diameter, the model can predict the resulting
three-dimensional CoW velocity field, pressure field, wall shear stress, and
outlet flow split under the specified outlet RCR assumptions.

If only one or both ICA velocities are measured, the vertebral artery inlet
flows still need measured values or explicit assumptions. Outlet RCR values
also strongly affect pressure and flow split. Absolute pressure requires
physiologic pressure calibration; the current table uses zero distal pressure,
so pressure should be interpreted as model gauge pressure unless calibrated.

The current Luisi-derived geometry is the intracranial CoW core. It does not
include the external carotid artery, superficial temporal/preauricular artery,
or common carotid artery. Measurements from those vessels can inform inlet
assumptions, but they cannot be directly assigned to missing branches without
extending the geometry and remeshing.
