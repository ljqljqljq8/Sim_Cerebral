from __future__ import annotations

from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
from importlib import import_module


ROOT = Path(__file__).resolve().parents[1]
SIMVASCULAR_APP = Path("/Applications/SimVascular.app")
SIMVASCULAR_CLI = SIMVASCULAR_APP / "Contents" / "Resources" / "simvascular"
KNOWN_SV_MULTIPHYSICS = [
    Path("/usr/local/sv/svMultiPhysics/2025-06-06/bin/svmultiphysics"),
]
PACKAGE_PROBES = ["numpy", "pandas", "yaml", "vtk", "pyvista", "meshio", "tetgen", "matplotlib", "scipy", "lxml"]


def command_exists(name: str) -> str | None:
    return shutil.which(name)


def find_svmultiphysics() -> str | None:
    found = command_exists("svmultiphysics")
    if found:
        return found
    for path in KNOWN_SV_MULTIPHYSICS:
        if path.exists() and os.access(path, os.X_OK):
            return str(path)
    return None


def run_probe(cmd: list[str], env: dict[str, str] | None = None, timeout: int = 20) -> dict:
    try:
        completed = subprocess.run(
            cmd,
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        return {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "stdout": completed.stdout.strip()[-4000:],
            "stderr": completed.stderr.strip()[-4000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "returncode": None,
            "stdout": (exc.stdout or "").strip()[-4000:] if isinstance(exc.stdout, str) else "",
            "stderr": "Timed out",
        }
    except Exception as exc:
        return {
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
        }


def app_python_env() -> tuple[Path | None, dict[str, str] | None]:
    if not SIMVASCULAR_APP.exists():
        return None, None
    sv_home = SIMVASCULAR_APP / "Contents" / "Resources"
    python = sv_home / "svExternals" / "bin" / "python3"
    if not python.exists():
        return None, None
    env = os.environ.copy()
    sv_ext = sv_home / "svExternals"
    lib_paths = [
        sv_home / "lib",
        sv_home / "lib" / "plugins",
        sv_home / "bin",
        sv_ext / "lib",
        sv_ext / "lib" / "plugins",
        sv_ext / "bin",
    ]
    python_paths = [
        sv_ext / "lib" / "python3.11" / "site-packages",
        sv_home / "Python3.11" / "site-packages",
        sv_home / "sv_rom_simulation_python",
    ]
    env["SV_HOME"] = str(sv_home)
    env["PYTHONHOME"] = str(sv_ext)
    env["PYTHONPATH"] = os.pathsep.join(str(p) for p in python_paths)
    env["DYLD_LIBRARY_PATH"] = os.pathsep.join(str(p) for p in lib_paths)
    env["DYLD_FALLBACK_FRAMEWORK_PATH"] = str(sv_ext / "lib")
    env["DYLD_FRAMEWORK_PATH"] = str(sv_ext / "lib")
    env["SV_PLUGIN_PATH"] = os.pathsep.join(str(p) for p in [sv_home / "lib" / "plugins", sv_ext / "lib" / "plugins"])
    env["HDF5_DISABLE_VERSION_CHECK"] = "1"
    return python, env


def main() -> None:
    report: dict[str, object] = {
        "project_root": str(ROOT),
        "python": sys.executable,
        "python_version": sys.version,
        "commands": {},
        "package_versions": {},
        "simvascular_app": {
            "path": str(SIMVASCULAR_APP),
            "exists": SIMVASCULAR_APP.exists(),
            "cli": str(SIMVASCULAR_CLI),
            "cli_exists": SIMVASCULAR_CLI.exists(),
        },
        "case_inputs": {},
        "probes": {},
        "recommendations": [],
    }

    for package in PACKAGE_PROBES:
        try:
            module = import_module(package)
            report["package_versions"][package] = getattr(module, "__version__", "available")
        except Exception as exc:
            report["package_versions"][package] = f"missing: {type(exc).__name__}: {exc}"

    for command in ["svpython", "mpiexec", "docker"]:
        report["commands"][command] = command_exists(command)
    report["commands"]["svmultiphysics"] = find_svmultiphysics()

    required_paths = {
        "stl": ROOT / "data_raw" / "luisi2024" / "extracted" / "CerebrovascularModel.stl",
        "capped_surface": ROOT / "cases" / "cow_luisi_mvp" / "geometry" / "surface_capped_cm.vtp",
        "mesh": ROOT / "cases" / "cow_luisi_mvp" / "mesh" / "mesh-complete.mesh.vtu",
        "solver_xml": ROOT / "cases" / "cow_luisi_mvp" / "solver" / "solver.xml",
    }
    report["case_inputs"] = {name: path.exists() for name, path in required_paths.items()}

    if report["commands"]["svpython"]:
        report["probes"]["svpython_import_sv"] = run_probe(
            [
                str(report["commands"]["svpython"]),
                "-c",
                "import sv; from sv import meshing; print(hasattr(meshing, 'TetGen'))",
            ]
        )
    else:
        report["recommendations"].append("No svpython command found. Use SimVascular wrapper '--python -- <script.py>' or fallback mesh.")

    if SIMVASCULAR_CLI.exists():
        report["probes"]["simvascular_cli_python_probe"] = run_probe(
            [str(SIMVASCULAR_CLI), "--python", "--", "scripts/probe_simvascular_python.py"],
            timeout=60,
        )
        if not report["probes"]["simvascular_cli_python_probe"]["ok"]:
            report["recommendations"].append(
                "SimVascular wrapper batch mode failed; inspect simvascular_cli_python_probe in this report."
            )

    app_python, env = app_python_env()
    if app_python and env:
        report["simvascular_app"]["python"] = str(app_python)
        report["probes"]["simvascular_app_python_import_sv"] = run_probe(
            [str(app_python), "-c", "import sv; from sv import meshing; print(hasattr(meshing, 'TetGen'))"],
            env=env,
        )
        if not report["probes"]["simvascular_app_python_import_sv"]["ok"]:
            report["recommendations"].append(
                "SimVascular.app bundled Python could not import sv directly from this shell; use the wrapper batch mode instead."
            )

    if report["commands"]["svmultiphysics"]:
        report["probes"]["svmultiphysics_exists"] = {"ok": True, "path": report["commands"]["svmultiphysics"]}
    else:
        report["recommendations"].append("No svmultiphysics executable found. Set SV_MULTIPHYSICS_BIN or install/build svMultiPhysics.")

    if not report["commands"]["docker"]:
        report["recommendations"].append("Docker is not available, so the documented solver container path cannot run here.")

    out = ROOT / "docs" / "runtime_status.json"
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    print(f"Wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
