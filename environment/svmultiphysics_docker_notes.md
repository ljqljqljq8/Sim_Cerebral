# svMultiPhysics Runtime Notes

The preprocessing scripts run with ordinary Python. Mesh generation needs
SimVascular Python because it imports `sv`.

Typical native commands:

```bash
svpython scripts/04_generate_tetgen_mesh.py
python scripts/utils_merge_wall.py
SV_MULTIPHYSICS_BIN=svmultiphysics MPI_NP=4 bash scripts/08_run_svmultiphysics.sh
```

If using Docker, mount the case directory and run from `solver/`:

```bash
cd cases/cow_luisi_mvp
docker run --rm -it \
  -v "$PWD:/case" \
  simvascular/solver:latest \
  bash -lc "cd /case/solver && mpirun --allow-run-as-root -n 4 /build-trilinos/svMultiPhysics-build/bin/svmultiphysics solver.xml"
```

Keep all solver outputs under `cases/cow_luisi_mvp/solver/` so
`scripts/09_postprocess_results.py` can find them.
