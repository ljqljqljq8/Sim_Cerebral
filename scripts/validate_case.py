from __future__ import annotations

from pathlib import Path
import json
import xml.etree.ElementTree as ET

import pandas as pd
import pyvista as pv
import yaml

from utils_vtk import count_boundary_edges, read_polydata


ROOT = Path(__file__).resolve().parents[1]


def require(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(path.relative_to(ROOT))


def main() -> None:
    cfg = yaml.safe_load((ROOT / "config" / "case_luisi.yaml").read_text())
    case_dir = ROOT / "cases" / cfg["case_name"]
    geom_dir = case_dir / "geometry"
    mesh_dir = case_dir / "mesh"
    bc_dir = case_dir / "bc"
    solver_dir = case_dir / "solver"
    faces = [*cfg["faces"]["inlets"], *cfg["faces"]["outlets"], cfg["faces"]["wall"]]

    for path in [
        geom_dir / "surface_capped_cm.vtp",
        geom_dir / "cap_metadata.csv",
        geom_dir / "face_map.json",
        bc_dir / "inlet_summary.csv",
        bc_dir / "rcr_values.csv",
        mesh_dir / "mesh-complete.mesh.vtu",
        solver_dir / "solver.xml",
    ]:
        require(path)

    capped = read_polydata(geom_dir / "surface_capped_cm.vtp")
    boundary_edges = count_boundary_edges(capped)
    if boundary_edges != 0:
        raise RuntimeError(f"Capped surface has {boundary_edges} boundary edges.")

    caps = pd.read_csv(geom_dir / "cap_metadata.csv")
    if len(caps) != int(cfg["geometry"]["expected_cap_count"]):
        raise RuntimeError(f"Expected 10 caps, found {len(caps)}.")
    assigned = set(caps["assigned_name"].dropna()) - {""}
    expected = set(cfg["faces"]["inlets"]) | set(cfg["faces"]["outlets"])
    if assigned != expected:
        raise RuntimeError(f"Face assignment mismatch: {assigned} != {expected}")

    for face in faces:
        require(mesh_dir / "mesh-surfaces" / f"{face}.vtp")
    for inlet in cfg["faces"]["inlets"]:
        require(bc_dir / f"{inlet}.flow")

    mesh = pv.read(mesh_dir / "mesh-complete.mesh.vtu")
    cell_types = sorted(set(mesh.celltypes.tolist()))
    if cell_types != [10]:
        raise RuntimeError(f"Expected tetrahedral mesh cell type [10], got {cell_types}.")

    ET.parse(solver_dir / "solver.xml")
    face_map = json.loads((geom_dir / "face_map.json").read_text())
    missing_names = expected - set(face_map)
    if missing_names:
        raise RuntimeError(f"face_map missing names: {sorted(missing_names)}")

    print("Validation passed.")
    print(f"  caps: {len(caps)}")
    print(f"  mesh cells: {mesh.n_cells}")
    print(f"  mesh points: {mesh.n_points}")
    print(f"  boundary edges: {boundary_edges}")


if __name__ == "__main__":
    main()

