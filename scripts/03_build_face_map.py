from __future__ import annotations

from pathlib import Path
import json

import pandas as pd
import yaml

from utils_vtk import read_polydata, write_polydata


ROOT = Path(__file__).resolve().parents[1]
CASE_CONFIG = ROOT / "config" / "case_luisi.yaml"
FACE_SCHEMA = ROOT / "config" / "face_schema.json"


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def sort_lr(rows: list[dict], axis: str, lower_axis_value_is_left: bool) -> list[dict]:
    key = f"c{axis}_cm"
    return sorted(rows, key=lambda row: row[key], reverse=not lower_axis_value_is_left)


def assign_luisi_heuristic(caps: list[dict], cfg: dict) -> dict[str, dict]:
    assignment_cfg = cfg.get("face_assignment", {})
    axis = assignment_cfg.get("left_right_axis", "x")
    lower_is_left = bool(assignment_cfg.get("lower_axis_value_is_left", True))
    pca_group = assignment_cfg.get("pca_group", "high_y")

    by_z = sorted(caps, key=lambda row: row["cz_cm"])
    lower_plane = by_z[:4]
    upper_plane = by_z[4:]
    if len(lower_plane) != 4 or len(upper_plane) != 6:
        raise RuntimeError(
            f"Luisi heuristic expects 4 inlet-plane caps and 6 outlet-plane caps, "
            f"got {len(lower_plane)} and {len(upper_plane)}."
        )

    lower_by_area = sorted(lower_plane, key=lambda row: row["area_mm2"], reverse=True)
    icas = sort_lr(lower_by_area[:2], axis, lower_is_left)
    vas = sort_lr(lower_by_area[2:], axis, lower_is_left)

    if pca_group == "high_y":
        pcas = sorted(upper_plane, key=lambda row: row["cy_cm"], reverse=True)[:2]
    elif pca_group == "low_y":
        pcas = sorted(upper_plane, key=lambda row: row["cy_cm"])[:2]
    else:
        raise ValueError(f"Unsupported pca_group: {pca_group}")
    pca_ids = {row["cap_id"] for row in pcas}
    anterior_middle = [row for row in upper_plane if row["cap_id"] not in pca_ids]
    if len(anterior_middle) != 4:
        raise RuntimeError("Luisi heuristic could not split PCA from ACA/MCA caps.")

    pcas_lr = sort_lr(pcas, axis, lower_is_left)
    am_lr = sort_lr(anterior_middle, axis, lower_is_left)

    named = {
        "LICA": icas[0],
        "RICA": icas[1],
        "LVA": vas[0],
        "RVA": vas[1],
        "LPCA": pcas_lr[0],
        "RPCA": pcas_lr[1],
        "LMCA": am_lr[0],
        "LACA": am_lr[1],
        "RACA": am_lr[2],
        "RMCA": am_lr[3],
    }
    return named


def build_face_map(named: dict[str, dict], schema: dict) -> dict:
    expected = schema["expected_area_mm2"]
    face_map = {}
    for name, row in named.items():
        kind = "inlet" if name in schema["inlets"] else "outlet"
        expected_area = expected.get(name)
        measured_area = float(row["area_mm2"])
        area_error_pct = None
        if expected_area:
            area_error_pct = 100.0 * (measured_area - expected_area) / expected_area
        face_map[name] = {
            "type": kind,
            "cap_id": int(row["cap_id"]),
            "sv_face_id": None,
            "area_mm2_expected": expected_area,
            "area_mm2_measured": measured_area,
            "area_error_pct": area_error_pct,
            "centroid_cm": [float(row["cx_cm"]), float(row["cy_cm"]), float(row["cz_cm"])],
            "normal": [float(row["nx"]), float(row["ny"]), float(row["nz"])],
            "pre_mesh_face_file": row["face_file"],
        }
    face_map[schema["wall"]] = {
        "type": "wall",
        "sv_face_ids": [],
        "pre_mesh_face_file": "cases/cow_luisi_mvp/geometry/faces_pre_mesh/wall.vtp",
    }
    return face_map


def main() -> None:
    cfg = yaml.safe_load(CASE_CONFIG.read_text())
    schema = json.loads(FACE_SCHEMA.read_text())
    case_dir = ROOT / "cases" / cfg["case_name"]
    geom_dir = case_dir / "geometry"
    face_dir = geom_dir / "faces_pre_mesh"
    metadata_path = geom_dir / "cap_metadata.csv"
    if not metadata_path.exists():
        raise FileNotFoundError(f"Missing {rel(metadata_path)}. Run scripts/02_clean_and_cap_surface.py first.")

    df = pd.read_csv(metadata_path)
    caps = df.to_dict(orient="records")
    named = assign_luisi_heuristic(caps, cfg)
    face_map = build_face_map(named, schema)

    assigned_by_id = {row["cap_id"]: name for name, row in named.items()}
    df["assigned_name"] = df["cap_id"].map(assigned_by_id).fillna("")
    df.to_csv(metadata_path, index=False)

    for name, row in named.items():
        src = face_dir / f"cap_{int(row['cap_id']):02d}.vtp"
        dst = face_dir / f"{name}.vtp"
        write_polydata(read_polydata(src), dst)

    face_map_path = geom_dir / "face_map.json"
    face_map_path.write_text(json.dumps(face_map, indent=2))
    qc_path = geom_dir / "face_assignment_qc.csv"
    pd.DataFrame(
        [
            {
                "name": name,
                "cap_id": info["cap_id"],
                "type": info["type"],
                "area_mm2_measured": info["area_mm2_measured"],
                "area_mm2_expected": info["area_mm2_expected"],
                "area_error_pct": info["area_error_pct"],
                "cx_cm": info["centroid_cm"][0],
                "cy_cm": info["centroid_cm"][1],
                "cz_cm": info["centroid_cm"][2],
            }
            for name, info in face_map.items()
            if name != schema["wall"]
        ]
    ).to_csv(qc_path, index=False)

    print(f"Wrote {rel(face_map_path)}")
    print(f"Wrote {rel(qc_path)}")
    print("Review the face assignment before production CFD.")


if __name__ == "__main__":
    main()

