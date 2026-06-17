from __future__ import annotations

from pathlib import Path
import argparse
import xml.dom.minidom as minidom
import xml.etree.ElementTree as ET

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]


def add_text(parent: ET.Element, tag: str, value, **attrs) -> ET.Element:
    elem = ET.SubElement(parent, tag, attrs)
    elem.text = f" {value} "
    return elem


def prettify(elem: ET.Element) -> str:
    raw = ET.tostring(elem, encoding="utf-8")
    return minidom.parseString(raw).toprettyxml(indent="  ")


def expected_inputs(case_dir: Path, faces: list[str]) -> list[Path]:
    paths = [case_dir / "mesh" / "mesh-complete.mesh.vtu"]
    paths.extend(case_dir / "mesh" / "mesh-surfaces" / f"{name}.vtp" for name in faces)
    return paths


def expected_mesh_inputs(case_dir: Path, mesh_subdir: str, faces: list[str]) -> list[Path]:
    paths = [case_dir / mesh_subdir / "mesh-complete.mesh.vtu"]
    paths.extend(case_dir / mesh_subdir / "mesh-surfaces" / f"{name}.vtp" for name in faces)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict-inputs", action="store_true", help="Fail if mesh and mesh-surfaces are missing.")
    parser.add_argument("--output", default="solver.xml", help="Solver XML file name to write inside the solver directory.")
    parser.add_argument("--n-steps", type=int, default=None, help="Override Number_of_time_steps, useful for smoke tests.")
    parser.add_argument("--dt", type=float, default=None, help="Override Time_step_size.")
    parser.add_argument("--save-every", type=int, default=None, help="Override Increment_in_saving_VTK_files.")
    parser.add_argument("--mesh-subdir", default="mesh", help="Case subdirectory containing mesh-complete.mesh.vtu.")
    parser.add_argument("--fluid-min-iterations", type=int, default=3, help="Fluid equation Min_iterations.")
    parser.add_argument("--fluid-max-iterations", type=int, default=5, help="Fluid equation Max_iterations.")
    parser.add_argument("--fluid-tolerance", default="1e-11", help="Fluid equation nonlinear tolerance.")
    parser.add_argument("--ls-max-iterations", type=int, default=15, help="Linear solver Max_iterations.")
    parser.add_argument("--ns-gm-max-iterations", type=int, default=10, help="NS GM max iterations.")
    parser.add_argument("--ns-cg-max-iterations", type=int, default=300, help="NS CG max iterations.")
    parser.add_argument("--ls-tolerance", default="1e-3", help="Linear solver tolerance.")
    parser.add_argument("--krylov-dimension", type=int, default=250, help="Linear solver Krylov space dimension.")
    args = parser.parse_args()

    cfg = yaml.safe_load((ROOT / "config" / "case_luisi.yaml").read_text())
    case_dir = ROOT / "cases" / cfg["case_name"]
    solver_dir = case_dir / "solver"
    solver_dir.mkdir(parents=True, exist_ok=True)

    rcr_path = case_dir / "bc" / "rcr_values.csv"
    if not rcr_path.exists():
        raise FileNotFoundError(f"Missing {rcr_path}. Run scripts/06_generate_rcr_table.py first.")
    rcr = pd.read_csv(rcr_path).set_index("face")

    inlets = list(cfg["faces"]["inlets"])
    outlets = list(cfg["faces"]["outlets"])
    wall = cfg["faces"]["wall"]
    all_faces = inlets + outlets + [wall]

    missing = [path for path in expected_mesh_inputs(case_dir, args.mesh_subdir, all_faces) if not path.exists()]
    if missing:
        msg = "Missing mesh inputs:\n" + "\n".join(f" - {p.relative_to(ROOT)}" for p in missing)
        if args.strict_inputs:
            raise FileNotFoundError(msg)
        print("[WARN]", msg)
        print("[WARN] Writing solver.xml anyway so the case is ready once meshing is complete.")

    sim = cfg["simulation"]
    period = float(sim["cardiac_period_s"])
    dt = float(args.dt if args.dt is not None else sim["dt_s"])
    n_steps = int(args.n_steps if args.n_steps is not None else round(period * int(sim["n_cycles"]) / dt))
    save_every = int(args.save_every if args.save_every is not None else sim["save_every_n_steps"])

    root = ET.Element("svMultiPhysicsFile", {"version": "0.1"})
    general = ET.SubElement(root, "GeneralSimulationParameters")
    add_text(general, "Continue_previous_simulation", "false")
    add_text(general, "Number_of_spatial_dimensions", 3)
    add_text(general, "Number_of_time_steps", n_steps)
    add_text(general, "Time_step_size", dt)
    add_text(general, "Spectral_radius_of_infinite_time_step", "0.50")
    add_text(general, "Searched_file_name_to_trigger_stop", "STOP_SIM")
    add_text(general, "Save_results_to_VTK_format", 1)
    add_text(general, "Name_prefix_of_saved_VTK_files", "result")
    add_text(general, "Increment_in_saving_VTK_files", save_every)
    add_text(general, "Start_saving_after_time_step", 1)
    add_text(general, "Increment_in_saving_restart_files", 100)
    add_text(general, "Convert_BIN_to_VTK_format", 0)
    add_text(general, "Verbose", 1)
    add_text(general, "Warning", 0)
    add_text(general, "Debug", 0)

    mesh = ET.SubElement(root, "Add_mesh", {"name": "msh"})
    add_text(mesh, "Mesh_file_path", f"../{args.mesh_subdir}/mesh-complete.mesh.vtu")
    for name in all_faces:
        face = ET.SubElement(mesh, "Add_face", {"name": name})
        add_text(face, "Face_file_path", f"../{args.mesh_subdir}/mesh-surfaces/{name}.vtp")

    eq = ET.SubElement(root, "Add_equation", {"type": "fluid"})
    add_text(eq, "Coupled", "true")
    add_text(eq, "Min_iterations", args.fluid_min_iterations)
    add_text(eq, "Max_iterations", args.fluid_max_iterations)
    add_text(eq, "Tolerance", args.fluid_tolerance)
    add_text(eq, "Backflow_stabilization_coefficient", 0.2)
    add_text(eq, "Density", cfg["blood"]["density_g_per_cm3"])
    viscosity = ET.SubElement(eq, "Viscosity", {"model": "Constant"})
    add_text(viscosity, "Value", cfg["blood"]["viscosity_g_per_cm_s"])

    spatial = ET.SubElement(eq, "Output", {"type": "Spatial"})
    for key in ["Velocity", "Pressure", "Traction", "Vorticity", "Divergence", "WSS"]:
        add_text(spatial, key, "true")
    b_int = ET.SubElement(eq, "Output", {"type": "B_INT"})
    add_text(b_int, "Pressure", "true")
    add_text(b_int, "Velocity", "true")
    v_int = ET.SubElement(eq, "Output", {"type": "V_INT"})
    add_text(v_int, "Pressure", "true")

    ls = ET.SubElement(eq, "LS", {"type": "NS"})
    la = ET.SubElement(ls, "Linear_algebra", {"type": "fsils"})
    add_text(la, "Preconditioner", "fsils")
    add_text(ls, "Max_iterations", args.ls_max_iterations)
    add_text(ls, "NS_GM_max_iterations", args.ns_gm_max_iterations)
    add_text(ls, "NS_CG_max_iterations", args.ns_cg_max_iterations)
    add_text(ls, "Tolerance", args.ls_tolerance)
    add_text(ls, "NS_GM_tolerance", args.ls_tolerance)
    add_text(ls, "NS_CG_tolerance", args.ls_tolerance)
    add_text(ls, "Absolute_tolerance", "1e-17")
    add_text(ls, "Krylov_space_dimension", args.krylov_dimension)

    for name in inlets:
        bc = ET.SubElement(eq, "Add_BC", {"name": name})
        add_text(bc, "Type", "Dir")
        add_text(bc, "Time_dependence", "Unsteady")
        add_text(bc, "Temporal_values_file_path", f"../bc/{name}.flow")
        add_text(bc, "Profile", "Parabolic")
        add_text(bc, "Impose_flux", "true")

    for name in outlets:
        row = rcr.loc[name]
        bc = ET.SubElement(eq, "Add_BC", {"name": name})
        add_text(bc, "Type", "Neu")
        add_text(bc, "Time_dependence", "RCR")
        values = ET.SubElement(bc, "RCR_values")
        add_text(values, "Capacitance", f"{row.C_cm5_dyn:.10e}")
        add_text(values, "Distal_resistance", f"{row.Rd_dyn_s_cm5:.10e}")
        add_text(values, "Proximal_resistance", f"{row.Rp_dyn_s_cm5:.10e}")
        add_text(values, "Distal_pressure", f"{row.Distal_pressure_dyn_cm2:.10e}")
        add_text(values, "Initial_pressure", f"{row.Initial_pressure_dyn_cm2:.10e}")

    bc = ET.SubElement(eq, "Add_BC", {"name": wall})
    add_text(bc, "Type", "Dir")
    add_text(bc, "Time_dependence", "Steady")
    add_text(bc, "Value", "0.0")

    out = solver_dir / args.output
    out.write_text(prettify(root))
    print("Wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
