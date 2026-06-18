#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import REPO_ROOT, copy_file, read_json, write_json


PROJECT_ROOT = REPO_ROOT.parent


def repo_rel(path: Path) -> str:
    return str(path.resolve().relative_to(REPO_ROOT))


def portable_value(value, replacements: list[tuple[str, str]]):
    if isinstance(value, str):
        text = value
        for src, dst in replacements:
            text = text.replace(src, dst)
        return text
    if isinstance(value, list):
        return [portable_value(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: portable_value(item, replacements) for key, item in value.items()}
    return value


def copy_tree_files(src_dir: Path, dst_dir: Path, patterns: list[str]) -> list[str]:
    copied = []
    for pattern in patterns:
        for src in sorted(src_dir.glob(pattern)):
            if src.is_file():
                dst = dst_dir / src.relative_to(src_dir)
                copy_file(src, dst)
                copied.append(repo_rel(dst))
    return copied


def main() -> int:
    parser = argparse.ArgumentParser(description="Copy the current cfd_v5/sv50 source case into sv50_repo.")
    parser.add_argument("--source-root", default="../cases/cfd_v5")
    parser.add_argument("--source-mesh-case", default="../cases/cfd_v5/sv50")
    parser.add_argument("--dest", default="case/sv50/source")
    args = parser.parse_args()

    source_root = (REPO_ROOT / args.source_root).resolve()
    source_mesh_case = (REPO_ROOT / args.source_mesh_case).resolve()
    dest = (REPO_ROOT / args.dest).resolve()
    dest.mkdir(parents=True, exist_ok=True)

    copied = []
    copied += copy_tree_files(
        source_root,
        dest,
        [
            "geo/cl.json",
            "geo/terms.json",
            "geo/surf_tet50d.vtp",
            "geo/surf_tet50d.stl",
            "reports/surf_tet50d_qc.json",
            "qc_diff/surf3_to_t50d_diff.json",
            "qc_diff/surf3_to_t50d_dist.vtp",
            "qc_diff/diff_front.png",
            "qc_diff/diff_right.png",
            "qc_diff/diff_top.png",
        ],
    )

    mesh_dest = dest / "sv50"
    copied += copy_tree_files(
        source_mesh_case,
        mesh_dest,
        [
            "face_labels.json",
            "mesh/mesh_status.json",
            "mesh/mesh-complete.mesh.vtu",
            "mesh/mesh-complete.exterior.vtp",
            "mesh/mesh-surfaces/*.vtp",
            "model/surface_model.vtp",
        ],
    )

    replacements = [
        (str(source_mesh_case), "case/sv50/source/sv50"),
        (str(source_root), "case/sv50/source"),
        (str(dest), "case/sv50/source"),
        (str(PROJECT_ROOT), "<original_Z-Anatomy-Simulation>"),
        (str(REPO_ROOT), "."),
    ]
    for rel_json in [
        "geo/cl.json",
        "qc_diff/surf3_to_t50d_diff.json",
        "sv50/face_labels.json",
        "sv50/mesh/mesh_status.json",
    ]:
        path = dest / rel_json
        if path.exists():
            write_json(path, portable_value(read_json(path), replacements))

    manifest = {
        "source_root": args.source_root,
        "source_mesh_case": args.source_mesh_case,
        "dest": args.dest,
        "copied_file_count": len(copied),
        "copied_files": copied,
        "portable_note": "This is a vendored copy for sv50_repo. Runtime executables are resolved from PATH or environment variables.",
    }
    write_json(dest / "vendor_manifest.json", manifest)
    print(f"vendored {len(copied)} files into {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
