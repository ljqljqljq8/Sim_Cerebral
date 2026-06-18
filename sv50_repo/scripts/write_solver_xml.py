#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import os
import xml.etree.ElementTree as ET
from pathlib import Path

from common import REPO_ROOT, load_yaml, read_json, resolve


def indent(elem: ET.Element, level: int = 0) -> None:
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for child in elem:
            indent(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = i
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def rel_to(path: Path, base: Path) -> str:
    return os.path.relpath(path.resolve(), base.resolve())


def repo_path(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else REPO_ROOT / p


def main() -> int:
    parser = argparse.ArgumentParser(description="Write svMultiPhysics XML for the clean sv50 case.")
    parser.add_argument("--case-dir", default="case/sv50")
    parser.add_argument("--config", default="configs/case.yaml")
    parser.add_argument("--n-steps", type=int, default=20)
    parser.add_argument("--cycles", type=float)
    parser.add_argument("--save-increment", type=int)
    parser.add_argument("--production", action="store_true")
    parser.add_argument("--out", default="simulation_truth/solver.xml")
    args = parser.parse_args()

    case_dir = resolve(args.case_dir)
    sim_dir = case_dir / "simulation_truth"
    out = case_dir / args.out
    config = load_yaml(args.config)
    solver = config.get("solver", {})
    blood = config.get("blood", {})
    faces = read_json(case_dir / "simvascular" / "face_labels.json")["faces"]
    bc = read_json(sim_dir / "bc_summary.json")
    rcr_rows = read_csv_rows(repo_path(bc["outlet_rcr_csv"]))

    dt = float(solver.get("time_step_s", 0.001))
    cycle_s = float(bc.get("cardiac_cycle_s", solver.get("cardiac_cycle_s", 0.8)))
    if args.cycles is not None:
        n_steps = max(1, int(round(float(args.cycles) * cycle_s / dt)))
    elif args.production:
        n_steps = max(1, int(round(float(solver.get("cycles_production", 5)) * cycle_s / dt)))
    else:
        n_steps = int(args.n_steps)
    save_inc = int(args.save_increment if args.save_increment is not None else solver.get("save_increment", 100))
    save_inc = max(1, min(save_inc, n_steps))

    root = ET.Element("svMultiPhysicsFile", version="0.1")
    general = ET.SubElement(root, "GeneralSimulationParameters")
    general_values = {
        "Continue_previous_simulation": "0",
        "Number_of_spatial_dimensions": "3",
        "Number_of_time_steps": str(n_steps),
        "Time_step_size": f"{dt:.8f}",
        "Spectral_radius_of_infinite_time_step": "0.50",
        "Searched_file_name_to_trigger_stop": "STOP_SIM",
        "Save_results_to_VTK_format": "1",
        "Name_prefix_of_saved_VTK_files": "result",
        "Increment_in_saving_VTK_files": str(save_inc),
        "Start_saving_after_time_step": "1",
        "Increment_in_saving_restart_files": str(save_inc),
        "Convert_BIN_to_VTK_format": "0",
        "Verbose": "1",
        "Warning": "0",
        "Debug": "0",
    }
    for key, value in general_values.items():
        ET.SubElement(general, key).text = value

    mesh_xml = ET.SubElement(root, "Add_mesh", name="msh")
    mesh_path = case_dir / "simvascular" / "mesh" / "mesh-complete.mesh.vtu"
    ET.SubElement(mesh_xml, "Mesh_file_path").text = rel_to(mesh_path, sim_dir)
    face_names = set()
    for face in faces:
        face_names.add(face["name"])
        face_xml = ET.SubElement(mesh_xml, "Add_face", name=face["name"])
        face_path = case_dir / "simvascular" / "mesh" / "mesh-surfaces" / face["surface_file"]
        ET.SubElement(face_xml, "Face_file_path").text = rel_to(face_path, sim_dir)

    equation = ET.SubElement(root, "Add_equation", type="fluid")
    ET.SubElement(equation, "Coupled").text = "true"
    ET.SubElement(equation, "Min_iterations").text = "3"
    ET.SubElement(equation, "Max_iterations").text = "12"
    ET.SubElement(equation, "Tolerance").text = "1e-11"
    ET.SubElement(equation, "Backflow_stabilization_coefficient").text = "0.2"
    ET.SubElement(equation, "Density").text = f"{float(blood.get('density_g_per_cm3', 1.06)):.8f}"
    viscosity = ET.SubElement(equation, "Viscosity", model="Constant")
    ET.SubElement(viscosity, "Value").text = f"{float(blood.get('viscosity_poise', 0.035)):.8f}"

    output = ET.SubElement(equation, "Output", type="Spatial")
    for name in ("Velocity", "Pressure", "Traction", "Vorticity", "Divergence", "WSS"):
        ET.SubElement(output, name).text = "true"

    linear_solver = ET.SubElement(equation, "LS", type="NS")
    algebra = ET.SubElement(linear_solver, "Linear_algebra", type="fsils")
    ET.SubElement(algebra, "Preconditioner").text = "fsils"
    ET.SubElement(linear_solver, "Max_iterations").text = "15"
    ET.SubElement(linear_solver, "NS_GM_max_iterations").text = "10"
    ET.SubElement(linear_solver, "NS_CG_max_iterations").text = "300"
    ET.SubElement(linear_solver, "Tolerance").text = "1e-3"
    ET.SubElement(linear_solver, "NS_GM_tolerance").text = "1e-3"
    ET.SubElement(linear_solver, "NS_CG_tolerance").text = "1e-3"
    ET.SubElement(linear_solver, "Absolute_tolerance").text = "1e-17"
    ET.SubElement(linear_solver, "Krylov_space_dimension").text = "250"

    for inlet, file_path in bc["inlet_flow_files"].items():
        if inlet not in face_names:
            raise SystemExit(f"Inlet face not found in mesh faces: {inlet}")
        inlet_bc = ET.SubElement(equation, "Add_BC", name=inlet)
        ET.SubElement(inlet_bc, "Type").text = "Dir"
        ET.SubElement(inlet_bc, "Time_dependence").text = "Unsteady"
        ET.SubElement(inlet_bc, "Temporal_values_file_path").text = rel_to(repo_path(file_path), sim_dir)
        ET.SubElement(inlet_bc, "Profile").text = str(solver.get("inlet_profile", "Parabolic"))
        ET.SubElement(inlet_bc, "Impose_flux").text = "true"

    for row in rcr_rows:
        outlet = row["outlet"]
        if outlet not in face_names:
            raise SystemExit(f"Outlet face not found in mesh faces: {outlet}")
        outlet_bc = ET.SubElement(equation, "Add_BC", name=outlet)
        ET.SubElement(outlet_bc, "Type").text = "Neu"
        ET.SubElement(outlet_bc, "Time_dependence").text = "RCR"
        values = ET.SubElement(outlet_bc, "RCR_values")
        ET.SubElement(values, "Capacitance").text = f"{float(row['C_cm3_per_barye']):.8g}"
        ET.SubElement(values, "Distal_resistance").text = f"{float(row['Rd_barye_s_per_cm3']):.8g}"
        ET.SubElement(values, "Proximal_resistance").text = f"{float(row['Rp_barye_s_per_cm3']):.8g}"
        ET.SubElement(values, "Distal_pressure").text = "0.0"
        ET.SubElement(values, "Initial_pressure").text = "0.0"

    if "WALL" in face_names:
        wall_bc = ET.SubElement(equation, "Add_BC", name="WALL")
        ET.SubElement(wall_bc, "Type").text = "Dir"
        ET.SubElement(wall_bc, "Time_dependence").text = "Steady"
        ET.SubElement(wall_bc, "Value").text = "0.0"

    notes = ET.SubElement(root, "Notes")
    ET.SubElement(notes, "Case").text = str(case_dir.resolve().relative_to(REPO_ROOT))
    ET.SubElement(notes, "BoundaryNames").text = "short_aliases"
    ET.SubElement(notes, "FaceCount").text = str(len(faces))
    ET.SubElement(notes, "NumberOfTimeSteps").text = str(n_steps)
    indent(root)
    out.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(out, encoding="utf-8", xml_declaration=True)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
