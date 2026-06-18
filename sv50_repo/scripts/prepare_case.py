#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import REPO_ROOT, copy_file, load_yaml, read_json, resolve, write_json


def alias_for(name: str, aliases: dict[str, str]) -> str:
    return aliases.get(name, name)


def short_surface_file(alias: str) -> str:
    return f"{alias}.vtp"


def repo_rel(path: Path) -> str:
    return str(path.resolve().relative_to(REPO_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare the clean sv50 solve case with short boundary names.")
    parser.add_argument("--config", default="configs/case.yaml")
    parser.add_argument("--aliases", default="configs/boundary_aliases.yaml")
    args = parser.parse_args()

    config = load_yaml(args.config)
    aliases = load_yaml(args.aliases).get("aliases", {})
    paths = config["paths"]
    source_root = resolve(paths["source_root"])
    source_mesh_case = resolve(paths["source_mesh_case"])
    if not source_root.exists() or not source_mesh_case.exists():
        raise SystemExit(
            "Vendored sv50 source case is missing. Run: "
            "python scripts/vendor_case.py"
        )
    case_dir = resolve(paths["case_dir"])
    mesh_src_dir = source_mesh_case / "mesh"
    mesh_dst_dir = case_dir / "simvascular" / "mesh"
    surf_dst_dir = mesh_dst_dir / "mesh-surfaces"

    for rel in ["config", "geometry", "simvascular/mesh/mesh-surfaces", "simulation_truth", "reports"]:
        (case_dir / rel).mkdir(parents=True, exist_ok=True)

    copy_file("configs/case.yaml", case_dir / "config" / "case.yaml")
    copy_file(source_root / "geo" / "surf_tet50d.vtp", case_dir / "geometry" / "surface_solve.vtp")
    copy_file(source_root / "geo" / "surf_tet50d.stl", case_dir / "geometry" / "surface_solve.stl")
    copy_file(source_root / "geo" / "terms.json", case_dir / "geometry" / "terminal_planes_original.json")
    copy_file(mesh_src_dir / "mesh-complete.mesh.vtu", mesh_dst_dir / "mesh-complete.mesh.vtu")
    copy_file(mesh_src_dir / "mesh-complete.exterior.vtp", mesh_dst_dir / "mesh-complete.exterior.vtp")

    source_faces = read_json(source_mesh_case / "face_labels.json")
    prepared_faces = []
    for face in source_faces.get("faces", []):
        original_name = face.get("name")
        if not original_name:
            continue
        alias = alias_for(original_name, aliases)
        src_file = mesh_src_dir / "mesh-surfaces" / face.get("surface_file", f"{original_name}.vtp")
        dst_file = surf_dst_dir / short_surface_file(alias)
        copy_file(src_file, dst_file)
        updated = dict(face)
        updated["original_name"] = original_name
        updated["name"] = alias
        updated["surface_file"] = dst_file.name
        updated["file"] = repo_rel(dst_file)
        updated["solver_face_path"] = f"../simvascular/mesh/mesh-surfaces/{dst_file.name}"
        prepared_faces.append(updated)

    face_labels = {
        "status": source_faces.get("status"),
        "surface_mesh_flag": source_faces.get("surface_mesh_flag"),
        "use_mmg": source_faces.get("use_mmg"),
        "global_edge_size_cm": source_faces.get("global_edge_size_cm"),
        "mesh_stats": source_faces.get("mesh_stats"),
        "tetgen_options": source_faces.get("tetgen_options"),
        "production_ready_terminal_caps": source_faces.get("production_ready_terminal_caps"),
        "failed_caps": source_faces.get("failed_caps", []),
        "mesh_file": repo_rel(mesh_dst_dir / "mesh-complete.mesh.vtu"),
        "exterior_file": repo_rel(mesh_dst_dir / "mesh-complete.exterior.vtp"),
        "surface_path": repo_rel(case_dir / "geometry" / "surface_solve.vtp"),
        "planes_path": repo_rel(case_dir / "geometry" / "terminal_planes.json"),
        "source_face_labels": repo_rel(source_mesh_case / "face_labels.json"),
        "boundary_aliases": aliases,
        "faces": prepared_faces,
    }
    write_json(case_dir / "simvascular" / "face_labels.json", face_labels)

    terminal_data = read_json(source_root / "geo" / "terms.json")
    prepared_terms = []
    for term in terminal_data.get("terminal_planes", []):
        original_name = term["name"]
        updated = dict(term)
        updated["original_name"] = original_name
        updated["name"] = alias_for(original_name, aliases)
        prepared_terms.append(updated)
    terminal_data["terminal_planes"] = prepared_terms
    terminal_data["boundary_aliases"] = aliases
    write_json(case_dir / "geometry" / "terminal_planes.json", terminal_data)

    role_counts: dict[str, int] = {}
    for face in prepared_faces:
        role_counts[face.get("role", "unknown")] = role_counts.get(face.get("role", "unknown"), 0) + 1
    manifest = {
        "case_dir": repo_rel(case_dir),
        "source_root": repo_rel(source_root),
        "source_mesh_case": repo_rel(source_mesh_case),
        "mesh": repo_rel(mesh_dst_dir / "mesh-complete.mesh.vtu"),
        "exterior": repo_rel(mesh_dst_dir / "mesh-complete.exterior.vtp"),
        "surface": repo_rel(case_dir / "geometry" / "surface_solve.vtp"),
        "face_labels": repo_rel(case_dir / "simvascular" / "face_labels.json"),
        "terminal_planes": repo_rel(case_dir / "geometry" / "terminal_planes.json"),
        "face_count": len(prepared_faces),
        "role_counts": role_counts,
        "terminal_plane_count": len(prepared_terms),
        "production_ready_terminal_caps": source_faces.get("production_ready_terminal_caps"),
    }
    write_json(case_dir / "case_manifest.json", manifest)
    print(f"prepared {case_dir}")
    print(f"faces {manifest['face_count']} terminals {manifest['terminal_plane_count']} roles {role_counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
