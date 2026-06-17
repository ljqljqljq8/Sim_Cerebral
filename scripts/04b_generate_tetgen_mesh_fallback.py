from __future__ import annotations

from pathlib import Path
import argparse
import json

import pyvista as pv
import tetgen
import yaml

from utils_vtk import read_polydata, write_polydata


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mesh-subdir", default="mesh", help="Case subdirectory for mesh outputs.")
    parser.add_argument("--global-edge-size-cm", type=float, default=None, help="Override max TetGen edge size.")
    args = parser.parse_args()

    cfg = yaml.safe_load((ROOT / "config" / "case_luisi.yaml").read_text())
    case_dir = ROOT / "cases" / cfg["case_name"]
    mesh_dir = case_dir / args.mesh_subdir
    surf_dir = mesh_dir / "mesh-surfaces"
    geom_faces = case_dir / "geometry" / "faces_pre_mesh"
    mesh_dir.mkdir(parents=True, exist_ok=True)
    surf_dir.mkdir(parents=True, exist_ok=True)

    surface_path = ROOT / cfg["geometry"]["capped_surface"]
    surface = pv.read(surface_path).triangulate().clean()
    max_edge = float(args.global_edge_size_cm if args.global_edge_size_cm is not None else cfg["mesh"].get("active_global_edge_size_cm", 0.06))
    max_volume = max_edge**3 / 6.0

    print("Running Python tetgen fallback.")
    print("This is for pipeline/debug use. Prefer SimVascular TetGen for production CFD.")
    print("Surface:", surface_path.relative_to(ROOT))
    print("Max volume target:", max_volume)

    generator = tetgen.TetGen(surface)
    generator.tetrahedralize(
        plc=True,
        quality=True,
        minratio=1.4,
        mindihedral=10.0,
        maxvolume=max_volume,
        quiet=False,
        verbose=1,
    )
    grid = generator.grid
    volume_path = mesh_dir / "mesh-complete.mesh.vtu"
    grid.save(volume_path)

    exterior = grid.extract_surface().triangulate().clean()
    exterior.save(mesh_dir / "mesh-complete.exterior.vtp")

    face_map_path = case_dir / "geometry" / "face_map.json"
    if face_map_path.exists():
        face_map = json.loads(face_map_path.read_text())
        for name in [*cfg["faces"]["inlets"], *cfg["faces"]["outlets"], cfg["faces"]["wall"]]:
            src = geom_faces / f"{name}.vtp"
            if src.exists():
                write_polydata(read_polydata(src), surf_dir / f"{name}.vtp")
        face_map["wall"]["sv_face_ids"] = ["fallback_python_tetgen_surface"]
        face_map_path.write_text(json.dumps(face_map, indent=2))

    print("Wrote", volume_path.relative_to(ROOT))
    print("Wrote", (mesh_dir / "mesh-complete.exterior.vtp").relative_to(ROOT))
    print("Copied named pre-mesh faces into mesh/mesh-surfaces for solver XML debugging.")


if __name__ == "__main__":
    main()
