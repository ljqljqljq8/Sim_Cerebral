from __future__ import annotations

from pathlib import Path
import json
import shutil

import pandas as pd
import yaml

from utils_units import MM2_TO_CM2
from utils_vtk import (
    append_polydata,
    boundary_loops,
    centroid,
    clean_polydata,
    count_boundary_edges,
    make_triangle_fan_cap,
    polygon_normal_and_area,
    prepare_polydata,
    read_polydata,
    scale_polydata,
    split_regions_by_feature_angle,
    surface_area,
    write_polydata,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "case_luisi.yaml"


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def resolve_raw_stl(cfg: dict) -> Path:
    raw_stl = ROOT / cfg["geometry"]["raw_stl"]
    if raw_stl.exists():
        return raw_stl

    candidates = sorted((ROOT / "data_raw" / "luisi2024" / "extracted").rglob("*.stl"))
    if len(candidates) == 1:
        print(f"Configured STL missing; using detected STL: {rel(candidates[0])}")
        return candidates[0]
    if candidates:
        raise FileNotFoundError(
            "Configured STL is missing and multiple STL candidates exist: "
            + ", ".join(rel(p) for p in candidates)
        )
    raise FileNotFoundError(f"Missing raw STL: {rel(raw_stl)}")


def sorted_cap_records(records: list[dict]) -> list[dict]:
    return sorted(records, key=lambda row: (row["cz_mm"], row["cx_mm"], row["cy_mm"]))


def write_cap_outputs(records: list[dict], face_dir: Path, scale: float) -> list[dict]:
    written = []
    for cap_id, record in enumerate(sorted_cap_records(records), start=1):
        poly_mm = record.pop("polydata_mm")
        poly_cm = scale_polydata(poly_mm, scale)
        cap_path = face_dir / f"cap_{cap_id:02d}.vtp"
        write_polydata(poly_cm, cap_path)
        row = {
            "cap_id": cap_id,
            "source": record["source"],
            "source_region_id": record.get("source_region_id"),
            "n_cells": poly_mm.GetNumberOfCells(),
            "area_mm2": record["area_mm2"],
            "area_cm2": record["area_mm2"] * MM2_TO_CM2,
            "cx_mm": record["cx_mm"],
            "cy_mm": record["cy_mm"],
            "cz_mm": record["cz_mm"],
            "cx_cm": record["cx_mm"] * scale,
            "cy_cm": record["cy_mm"] * scale,
            "cz_cm": record["cz_mm"] * scale,
            "nx": record["nx"],
            "ny": record["ny"],
            "nz": record["nz"],
            "assigned_name": "",
            "face_file": rel(cap_path),
        }
        written.append(row)
    return written


def preprocess_open_surface(clean_mm, cfg: dict, out_dir: Path, face_dir: Path) -> tuple[object, object, list[dict]]:
    loops = boundary_loops(clean_mm)
    if not loops:
        raise RuntimeError("Boundary edge count is nonzero but no loops could be ordered.")

    cap_records = []
    cap_polys = []
    for loop_index, points in enumerate(loops, start=1):
        normal, area_mm2 = polygon_normal_and_area(points)
        center = centroid(make_triangle_fan_cap(points))
        cap = make_triangle_fan_cap(points)
        cap_polys.append(cap)
        cap_records.append(
            {
                "source": "auto_triangle_fan_from_open_loop",
                "source_region_id": loop_index,
                "area_mm2": area_mm2,
                "cx_mm": center[0],
                "cy_mm": center[1],
                "cz_mm": center[2],
                "nx": normal[0],
                "ny": normal[1],
                "nz": normal[2],
                "polydata_mm": cap,
            }
        )

    capped_mm = append_polydata([clean_mm, *cap_polys])
    return clean_mm, capped_mm, cap_records


def preprocess_closed_surface(clean_mm, cfg: dict, out_dir: Path, face_dir: Path) -> tuple[object, object, list[dict]]:
    feature_angle = float(cfg["geometry"].get("closed_cap_feature_angle_deg", 25.0))
    min_area = float(cfg["geometry"].get("min_cap_area_mm2", 5.0))
    expected_count = int(cfg["geometry"].get("expected_cap_count", 10))

    regions = split_regions_by_feature_angle(clean_mm, feature_angle)
    regions_by_area = sorted(regions, key=lambda r: r.area, reverse=True)
    wall_region = regions_by_area[0]
    candidates = [r for r in regions_by_area[1:] if r.area >= min_area]
    if len(candidates) > expected_count:
        print(
            f"Detected {len(candidates)} cap-like regions; keeping the {expected_count} largest "
            "after filtering tiny artifacts."
        )
        candidates = sorted(candidates, key=lambda r: r.area, reverse=True)[:expected_count]
    if len(candidates) != expected_count:
        print(f"[WARN] Expected {expected_count} caps, detected {len(candidates)}.")

    scale = float(cfg["geometry"].get("scale_mm_to_cm", 0.1))
    write_polydata(scale_polydata(wall_region.polydata, scale), face_dir / "wall.vtp")

    records = []
    for region in candidates:
        records.append(
            {
                "source": "existing_planar_cap_from_closed_stl",
                "source_region_id": region.region_id,
                "area_mm2": region.area,
                "cx_mm": region.centroid[0],
                "cy_mm": region.centroid[1],
                "cz_mm": region.centroid[2],
                "nx": region.normal[0],
                "ny": region.normal[1],
                "nz": region.normal[2],
                "polydata_mm": region.polydata,
            }
        )

    return wall_region.polydata, clean_mm, records


def main() -> None:
    cfg = yaml.safe_load(CONFIG.read_text())
    case_dir = ROOT / "cases" / cfg["case_name"]
    out_dir = case_dir / "geometry"
    face_dir = out_dir / "faces_pre_mesh"
    out_dir.mkdir(parents=True, exist_ok=True)
    face_dir.mkdir(parents=True, exist_ok=True)

    raw_stl = resolve_raw_stl(cfg)
    case_raw = out_dir / "raw.stl"
    if not case_raw.exists():
        shutil.copyfile(raw_stl, case_raw)

    raw = read_polydata(raw_stl)
    clean_mm = prepare_polydata(raw)
    open_clean_path = out_dir / "surface_open_clean_mm.vtp"
    write_polydata(clean_mm, open_clean_path)

    boundary_edge_count = count_boundary_edges(clean_mm)
    scale = float(cfg["geometry"].get("scale_mm_to_cm", 0.1))

    if boundary_edge_count > 0:
        wall_mm, capped_mm, cap_records = preprocess_open_surface(clean_mm, cfg, out_dir, face_dir)
        write_polydata(scale_polydata(wall_mm, scale), face_dir / "wall.vtp")
        preprocessing_mode = "open_surface_auto_cap"
    else:
        wall_mm, capped_mm, cap_records = preprocess_closed_surface(clean_mm, cfg, out_dir, face_dir)
        preprocessing_mode = "closed_surface_existing_caps"

    capped_cm = scale_polydata(capped_mm, scale)
    capped_path = ROOT / cfg["geometry"]["capped_surface"]
    write_polydata(capped_cm, capped_path)

    metadata = write_cap_outputs(cap_records, face_dir, scale)
    metadata_path = out_dir / "cap_metadata.csv"
    pd.DataFrame(metadata).to_csv(metadata_path, index=False)

    summary = {
        "raw_stl": rel(raw_stl),
        "mode": preprocessing_mode,
        "boundary_edge_count_before": boundary_edge_count,
        "points": clean_mm.GetNumberOfPoints(),
        "cells": clean_mm.GetNumberOfCells(),
        "cap_count": len(metadata),
        "capped_surface": rel(capped_path),
        "cap_metadata": rel(metadata_path),
        "faces_pre_mesh": rel(face_dir),
    }
    summary_path = out_dir / "preprocess_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

