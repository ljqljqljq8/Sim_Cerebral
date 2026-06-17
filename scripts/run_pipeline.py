from __future__ import annotations

from pathlib import Path
import argparse
import os
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], env: dict[str, str] | None = None) -> None:
    print("\n$", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True, env=env)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CoW automation steps.")
    parser.add_argument("--skip-download", action="store_true", help="Do not call scripts/00_download_luisi.sh.")
    parser.add_argument("--with-mesh", action="store_true", help="Run SimVascular TetGen step with svpython.")
    parser.add_argument("--with-fallback-mesh", action="store_true", help="Run ordinary Python tetgen fallback mesh step.")
    parser.add_argument("--with-solver", action="store_true", help="Run svMultiPhysics after mesh and XML generation.")
    parser.add_argument("--check-runtime", action="store_true", help="Write docs/runtime_status.json before running.")
    parser.add_argument("--validate", action="store_true", help="Run scripts/validate_case.py at the end.")
    parser.add_argument("--mesh-subdir", default="mesh", help="Case subdirectory for mesh inputs/outputs.")
    parser.add_argument("--global-edge-size-cm", type=float, default=None, help="Override SimVascular TetGen global edge size.")
    parser.add_argument("--cap-edge-size-cm", type=float, default=None, help="Override SimVascular TetGen cap-local edge size.")
    parser.add_argument("--solver-xml", default="solver.xml", help="Solver XML file name inside the solver directory.")
    parser.add_argument("--solver-steps", type=int, default=None, help="Override solver time steps.")
    parser.add_argument("--save-every", type=int, default=None, help="Override solver VTK save increment.")
    parser.add_argument("--svpython", default="svpython", help="SimVascular Python executable.")
    parser.add_argument(
        "--simvascular-cli",
        default="/Applications/SimVascular.app/Contents/Resources/simvascular",
        help="SimVascular wrapper executable supporting '--python -- <script.py>'.",
    )
    args = parser.parse_args()

    py = sys.executable
    if args.check_runtime:
        run([py, "scripts/check_runtime.py"])
    if not args.skip_download:
        run(["bash", "scripts/00_download_luisi.sh"])
    run([py, "scripts/01_unpack_and_inspect.py"])
    run([py, "scripts/02_clean_and_cap_surface.py"])
    run([py, "scripts/03_build_face_map.py"])
    run([py, "scripts/05_generate_inlet_waveforms.py"])
    run([py, "scripts/06_generate_rcr_table.py"])

    if args.with_mesh:
        mesh_args = ["--mesh-subdir", args.mesh_subdir]
        if args.global_edge_size_cm is not None:
            mesh_args.extend(["--global-edge-size-cm", str(args.global_edge_size_cm)])
        if args.cap_edge_size_cm is not None:
            mesh_args.extend(["--cap-edge-size-cm", str(args.cap_edge_size_cm)])
        if Path(args.simvascular_cli).exists():
            run([args.simvascular_cli, "--python", "--", "scripts/04_generate_tetgen_mesh.py", *mesh_args])
        else:
            run([args.svpython, "scripts/04_generate_tetgen_mesh.py", *mesh_args])
        run([py, "scripts/utils_merge_wall.py", "--mesh-subdir", args.mesh_subdir])
    elif args.with_fallback_mesh:
        fallback_args = ["--mesh-subdir", args.mesh_subdir]
        if args.global_edge_size_cm is not None:
            fallback_args.extend(["--global-edge-size-cm", str(args.global_edge_size_cm)])
        run([py, "scripts/04b_generate_tetgen_mesh_fallback.py", *fallback_args])

    xml_args = ["--output", args.solver_xml, "--mesh-subdir", args.mesh_subdir]
    if args.with_mesh or args.with_fallback_mesh:
        xml_args.append("--strict-inputs")
    if args.solver_steps is not None:
        xml_args.extend(["--n-steps", str(args.solver_steps)])
    if args.save_every is not None:
        xml_args.extend(["--save-every", str(args.save_every)])
    run([py, "scripts/07_write_svmultiphysics_xml.py", *xml_args])

    if args.with_solver:
        env = os.environ.copy()
        env["SOLVER_XML"] = args.solver_xml
        run(["bash", "scripts/08_run_svmultiphysics.sh"], env=env)
        run([py, "scripts/09_postprocess_results.py"])
    else:
        run([py, "scripts/09_postprocess_results.py"])

    if args.validate:
        run([py, "scripts/validate_case.py"])


if __name__ == "__main__":
    main()
