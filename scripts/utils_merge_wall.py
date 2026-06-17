from __future__ import annotations

from pathlib import Path
import argparse

import vtk

from utils_vtk import read_polydata, write_polydata


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mesh-subdir", default="mesh", help="Case subdirectory containing mesh-surfaces.")
    args = parser.parse_args()

    surf_dir = ROOT / "cases" / "cow_luisi_mvp" / args.mesh_subdir / "mesh-surfaces"
    files = sorted(surf_dir.glob("wall_*.vtp"))
    if not files:
        fallback = ROOT / "cases" / "cow_luisi_mvp" / "geometry" / "faces_pre_mesh" / "wall.vtp"
        if fallback.exists():
            write_polydata(read_polydata(fallback), surf_dir / "wall.vtp")
            print("No mesh wall_* faces found; copied pre-mesh wall to mesh-surfaces/wall.vtp")
            return
        raise FileNotFoundError(f"No wall_*.vtp files under {surf_dir}")

    append = vtk.vtkAppendPolyData()
    for path in files:
        append.AddInputData(read_polydata(path))
    append.Update()
    clean = vtk.vtkCleanPolyData()
    clean.SetInputData(append.GetOutput())
    clean.Update()
    out = surf_dir / "wall.vtp"
    write_polydata(clean.GetOutput(), out)
    print("written", out)


if __name__ == "__main__":
    main()
