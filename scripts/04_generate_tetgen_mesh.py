from __future__ import annotations

from pathlib import Path
import argparse
import csv
import json
import math

import vtk

try:
    import sv
    from sv import meshing
except Exception as exc:  # pragma: no cover - this must run in SimVascular Python.
    raise SystemExit(
        "This script must run in a SimVascular Python environment that can import sv. "
        "Try: svpython scripts/04_generate_tetgen_mesh.py"
    ) from exc

from utils_vtk import append_polydata, centroid, read_polydata, surface_area, write_polydata


ROOT = Path(__file__).resolve().parents[1]


def load_yaml_config() -> dict:
    try:
        import yaml

        return yaml.safe_load((ROOT / "config" / "case_luisi.yaml").read_text())
    except Exception:
        return {
            "case_name": "cow_luisi_mvp",
            "geometry": {"capped_surface": "cases/cow_luisi_mvp/geometry/surface_capped_cm.vtp"},
            "mesh": {
                "boundary_face_angle_deg": 25.0,
                "active_global_edge_size_cm": 0.06,
                "cap_local_edge_size_cm": 0.04,
                "quality_ratio": 1.4,
                "optimization": 3,
                "use_mmg": True,
                "boundary_layer": {
                    "enabled": True,
                    "number_of_layers": 3,
                    "edge_size_fraction": 0.35,
                    "layer_decreasing_ratio": 0.7,
                    "constant_thickness": False,
                },
            },
        }


def distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((float(a[i]) - float(b[i])) ** 2 for i in range(3)))


def read_cap_metadata(path: Path) -> dict[int, dict]:
    with path.open(newline="") as stream:
        rows = {}
        for row in csv.DictReader(stream):
            cap_id = int(row["cap_id"])
            rows[cap_id] = {
                "cap_id": cap_id,
                "area_cm2": float(row["area_cm2"]),
                "centroid_cm": [float(row["cx_cm"]), float(row["cy_cm"]), float(row["cz_cm"])],
            }
    return rows


def with_model_face_id(polydata: vtk.vtkPolyData, face_id: int) -> vtk.vtkPolyData:
    output = vtk.vtkPolyData()
    output.DeepCopy(polydata)
    ids = vtk.vtkIntArray()
    ids.SetName("ModelFaceID")
    ids.SetNumberOfComponents(1)
    ids.SetNumberOfTuples(output.GetNumberOfCells())
    for cell_id in range(output.GetNumberOfCells()):
        ids.SetValue(cell_id, int(face_id))
    output.GetCellData().SetScalars(ids)
    output.GetCellData().SetActiveScalars("ModelFaceID")
    return output


def build_model_face_id_surface(case_dir: Path, geom_dir: Path, face_map: dict) -> Path:
    pieces = []
    wall_info = face_map.get("wall")
    if not wall_info:
        raise RuntimeError("face_map.json does not define a wall entry.")

    wall_face_id = 1
    wall_path = ROOT / wall_info["pre_mesh_face_file"]
    pieces.append(with_model_face_id(read_polydata(wall_path), wall_face_id))
    wall_info["sv_face_ids"] = [wall_face_id]

    for name, info in face_map.items():
        if name == "wall":
            continue
        face_id = int(info["cap_id"]) + 1
        face_path = ROOT / info["pre_mesh_face_file"]
        pieces.append(with_model_face_id(read_polydata(face_path), face_id))
        info["sv_face_id"] = face_id

    model = append_polydata(pieces)
    output_path = geom_dir / "surface_capped_model_face_id.vtp"
    write_polydata(model, output_path)
    return output_path


def match_sv_faces(face_map: dict, cap_metadata: dict[int, dict], sv_faces: list[dict]) -> list[dict]:
    unmatched = {face["fid"]: face for face in sv_faces}
    report = []
    for name, info in face_map.items():
        if name == "wall":
            continue
        cap = cap_metadata[int(info["cap_id"])]
        best = None
        for fid, sv_face in unmatched.items():
            area_ref = max(cap["area_cm2"], 1.0e-12)
            area_rel = abs(sv_face["area_cm2"] - cap["area_cm2"]) / area_ref
            dist = distance(sv_face["centroid_cm"], cap["centroid_cm"])
            score = area_rel + 10.0 * dist
            candidate = (score, fid, area_rel, dist, sv_face)
            if best is None or candidate < best:
                best = candidate
        if best is None:
            raise RuntimeError(f"Could not match SimVascular face for {name}")
        score, fid, area_rel, dist, sv_face = best
        unmatched.pop(fid)
        info["sv_face_id"] = int(fid)
        report.append(
            {
                "name": name,
                "cap_id": int(info["cap_id"]),
                "sv_face_id": int(fid),
                "cap_area_cm2": cap["area_cm2"],
                "sv_area_cm2": sv_face["area_cm2"],
                "area_rel_error": area_rel,
                "centroid_distance_cm": dist,
                "match_score": score,
            }
        )
    face_map["wall"]["sv_face_ids"] = sorted(int(fid) for fid in unmatched)
    return report


def build_face_id_report(face_map: dict, cap_metadata: dict[int, dict]) -> list[dict]:
    report = []
    for name, info in face_map.items():
        if name == "wall":
            continue
        cap = cap_metadata[int(info["cap_id"])]
        pd = read_polydata(ROOT / info["pre_mesh_face_file"])
        area_cm2 = surface_area(pd)
        center = list(centroid(pd))
        area_ref = max(cap["area_cm2"], 1.0e-12)
        area_rel = abs(area_cm2 - cap["area_cm2"]) / area_ref
        dist = distance(center, cap["centroid_cm"])
        report.append(
            {
                "name": name,
                "cap_id": int(info["cap_id"]),
                "sv_face_id": int(info["sv_face_id"]),
                "cap_area_cm2": cap["area_cm2"],
                "sv_area_cm2": area_cm2,
                "area_rel_error": area_rel,
                "centroid_distance_cm": dist,
                "match_score": area_rel + 10.0 * dist,
            }
        )
    return report


def set_option_if_present(options, attr: str, value) -> None:
    try:
        setattr(options, attr, value)
    except Exception:
        print(f"[WARN] TetGenOptions does not accept {attr}={value!r} in this SimVascular version.")


def apply_boundary_layer_options(mesher, mesh_cfg: dict) -> None:
    bl = mesh_cfg.get("boundary_layer", {})
    mesher.set_boundary_layer_options(
        number_of_layers=int(bl.get("number_of_layers", 3)),
        edge_size_fraction=float(bl.get("edge_size_fraction", 0.35)),
        layer_decreasing_ratio=float(bl.get("layer_decreasing_ratio", 0.7)),
        constant_thickness=bool(bl.get("constant_thickness", False)),
    )


def create_tetgen_options(
    mesh_cfg: dict,
    face_map: dict,
    use_mmg: bool | None = None,
    global_edge_size_override: float | None = None,
    cap_edge_size_override: float | None = None,
):
    global_edge_size = float(
        global_edge_size_override
        if global_edge_size_override is not None
        else mesh_cfg.get("active_global_edge_size_cm", 0.06)
    )
    options = meshing.TetGenOptions(global_edge_size=global_edge_size, surface_mesh_flag=True, volume_mesh_flag=True)
    set_option_if_present(options, "optimization", int(mesh_cfg.get("optimization", 3)))
    set_option_if_present(options, "quality_ratio", float(mesh_cfg.get("quality_ratio", 1.4)))
    if use_mmg is None:
        use_mmg = bool(mesh_cfg.get("use_mmg", True))
    set_option_if_present(options, "use_mmg", bool(use_mmg))

    cap_edge = float(
        cap_edge_size_override if cap_edge_size_override is not None else mesh_cfg.get("cap_local_edge_size_cm", global_edge_size)
    )
    try:
        options.local_edge_size_on = True
        for name, info in face_map.items():
            if name != "wall":
                options.create_local_edge_size(int(info["sv_face_id"]), cap_edge)
    except Exception as exc:
        print(f"[WARN] Local cap edge size was not applied: {exc}")
    return options


def create_configured_mesher(
    model: Path,
    angle: float,
    expected_ids: set[int],
    wall_ids: list[int],
    mesh_cfg: dict,
    apply_boundary_layer: bool,
):
    mesher = meshing.TetGen()
    mesher.load_model(str(model))
    face_ids = [int(fid) for fid in mesher.get_model_face_ids()]
    missing = sorted(expected_ids - set(face_ids))
    if missing:
        raise RuntimeError(f"SimVascular did not read expected ModelFaceID values: {missing}")

    if not wall_ids:
        raise RuntimeError("No wall faces remain after cap matching.")
    mesher.set_walls(wall_ids)

    if apply_boundary_layer:
        apply_boundary_layer_options(mesher, mesh_cfg)
    return mesher, face_ids


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mesh-subdir", default="mesh", help="Case subdirectory for mesh outputs.")
    parser.add_argument("--global-edge-size-cm", type=float, default=None, help="Override global TetGen edge size.")
    parser.add_argument("--cap-edge-size-cm", type=float, default=None, help="Override cap-local TetGen edge size.")
    args = parser.parse_args()

    cfg = load_yaml_config()
    case_dir = ROOT / "cases" / cfg["case_name"]
    geom_dir = case_dir / "geometry"
    mesh_dir = case_dir / args.mesh_subdir
    surf_dir = mesh_dir / "mesh-surfaces"
    mesh_dir.mkdir(parents=True, exist_ok=True)
    surf_dir.mkdir(parents=True, exist_ok=True)

    source_model = ROOT / cfg["geometry"]["capped_surface"]
    face_map_path = geom_dir / "face_map.json"
    cap_metadata_path = geom_dir / "cap_metadata.csv"
    if not source_model.exists():
        raise FileNotFoundError(source_model)
    if not face_map_path.exists():
        raise FileNotFoundError(f"Missing {face_map_path}. Run scripts/03_build_face_map.py first.")

    face_map = json.loads(face_map_path.read_text())
    cap_metadata = read_cap_metadata(cap_metadata_path)
    mesh_cfg = cfg.get("mesh", {})
    model = build_model_face_id_surface(case_dir, geom_dir, face_map)

    angle = float(mesh_cfg.get("boundary_face_angle_deg", 25.0))
    expected_ids = {int(info["sv_face_id"]) for name, info in face_map.items() if name != "wall"}
    expected_ids.update(int(fid) for fid in face_map["wall"]["sv_face_ids"])

    report = build_face_id_report(face_map, cap_metadata)
    with (mesh_dir / "sv_face_matching_report.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(report[0].keys()))
        writer.writeheader()
        writer.writerows(report)
    face_map_path.write_text(json.dumps(face_map, indent=2))

    wall_ids = [int(fid) for fid in face_map["wall"]["sv_face_ids"]]
    if not wall_ids:
        raise RuntimeError("No wall faces remain after cap matching.")

    boundary_layer_enabled = bool(mesh_cfg.get("boundary_layer", {}).get("enabled", True))
    attempts = [
        {
            "name": "configured",
            "use_mmg": None,
            "boundary_layer": boundary_layer_enabled,
        }
    ]
    if (not boundary_layer_enabled) and bool(mesh_cfg.get("use_mmg", True)):
        attempts.append({"name": "without_boundary_layer_or_mmg", "use_mmg": False, "boundary_layer": False})

    generation_errors = []
    mesher = None
    face_ids = []
    successful_attempt = None
    for attempt in attempts:
        try:
            mesher, face_ids = create_configured_mesher(
                model=model,
                angle=angle,
                expected_ids=expected_ids,
                wall_ids=wall_ids,
                mesh_cfg=mesh_cfg,
                apply_boundary_layer=bool(attempt["boundary_layer"]),
            )
            options = create_tetgen_options(
                mesh_cfg,
                face_map,
                use_mmg=attempt["use_mmg"],
                global_edge_size_override=args.global_edge_size_cm,
                cap_edge_size_override=args.cap_edge_size_cm,
            )
            mesher.generate_mesh(options)
            successful_attempt = attempt
            break
        except Exception as exc:
            generation_errors.append({"attempt": attempt["name"], "error": str(exc)})
            print(f"[WARN] TetGen attempt '{attempt['name']}' failed: {exc}")

    if mesher is None or successful_attempt is None:
        raise RuntimeError(f"All SimVascular TetGen attempts failed: {generation_errors}")

    (mesh_dir / "mesh_generation_report.json").write_text(
        json.dumps(
            {
                "model": str(model.relative_to(ROOT)),
                "mesh_subdir": args.mesh_subdir,
                "global_edge_size_cm": args.global_edge_size_cm
                if args.global_edge_size_cm is not None
                else mesh_cfg.get("active_global_edge_size_cm", 0.06),
                "cap_edge_size_cm": args.cap_edge_size_cm
                if args.cap_edge_size_cm is not None
                else mesh_cfg.get("cap_local_edge_size_cm", mesh_cfg.get("active_global_edge_size_cm", 0.06)),
                "face_ids": face_ids,
                "successful_attempt": successful_attempt,
                "failed_attempts": generation_errors,
            },
            indent=2,
        )
    )
    volume_path = mesh_dir / "mesh-complete.mesh.vtu"
    mesher.write_mesh(str(volume_path))

    for name, info in face_map.items():
        if name == "wall":
            for fid in info["sv_face_ids"]:
                write_polydata(mesher.get_face_polydata(fid), surf_dir / f"wall_{fid}.vtp")
        else:
            write_polydata(mesher.get_face_polydata(info["sv_face_id"]), surf_dir / f"{name}.vtp")

    try:
        write_polydata(mesher.get_surface(), mesh_dir / "mesh-complete.exterior.vtp")
    except Exception:
        pass

    print("Mesh written to:", volume_path)
    print("Run: python scripts/utils_merge_wall.py")


if __name__ == "__main__":
    main()
