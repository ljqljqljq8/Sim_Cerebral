from __future__ import annotations

from pathlib import Path
import argparse
import json
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "cases" / "cow_luisi_mvp"
SOLVER_DIR = CASE / "solver"
RUN_LOG = SOLVER_DIR / "solver_production_hifi_save20_np6.run.log"
OUTPUT_DIR = SOLVER_DIR / "6-procs"
SOLVER_XML = SOLVER_DIR / "solver_production_hifi_save20.xml"
PROGRESS_JSON = SOLVER_DIR / "solver_production_hifi_save20_np6.progress.json"
CONVERGENCE_JSON = SOLVER_DIR / "solver_production_hifi_save20_np6.convergence.json"
POST_DIR = CASE / "results" / "post_hifi_np6_live"
WATCH_JSON = SOLVER_DIR / "solver_production_hifi_save20_np6.autowatch.json"
VTU_VERIFY_JSON = POST_DIR / "first_vtu_verification.json"


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def verify_first_vtu() -> dict | None:
    if VTU_VERIFY_JSON.exists():
        return load_json(VTU_VERIFY_JSON)
    vtus = sorted(OUTPUT_DIR.glob("result_*.vtu"))
    if not vtus:
        return None
    first = vtus[0]
    import pyvista as pv

    mesh = pv.read(first)
    result = {
        "verified_epoch": time.time(),
        "vtu": str(first.relative_to(ROOT)),
        "n_cells": int(mesh.n_cells),
        "n_points": int(mesh.n_points),
        "array_names": list(mesh.array_names),
        "bounds": [float(value) for value in mesh.bounds],
    }
    POST_DIR.mkdir(parents=True, exist_ok=True)
    VTU_VERIFY_JSON.write_text(json.dumps(result, indent=2))
    return result


def poll_once() -> dict:
    status_run = run(
        [
            sys.executable,
            "scripts/check_production_solve_status.py",
            "--run-log",
            str(RUN_LOG.relative_to(ROOT)),
            "--output-dir",
            str(OUTPUT_DIR.relative_to(ROOT)),
            "--status-out",
            str(PROGRESS_JSON.relative_to(ROOT)),
            "--solver-xml",
            str(SOLVER_XML.relative_to(ROOT)),
        ]
    )
    convergence_run = run(
        [
            sys.executable,
            "scripts/analyze_solver_log.py",
            "--log",
            str(RUN_LOG.relative_to(ROOT)),
            "--output",
            str(CONVERGENCE_JSON.relative_to(ROOT)),
        ]
    )
    post_run = run(
        [
            sys.executable,
            "scripts/09_postprocess_results.py",
            "--solver-output-dir",
            str(OUTPUT_DIR.relative_to(ROOT)),
            "--post-dir",
            str(POST_DIR.relative_to(ROOT)),
        ]
    )

    vtu_verification = None
    vtu_error = None
    try:
        vtu_verification = verify_first_vtu()
    except Exception as exc:  # noqa: BLE001 - persisted in status for inspection.
        vtu_error = repr(exc)

    status = load_json(PROGRESS_JSON)
    convergence = load_json(CONVERGENCE_JSON)
    watch = {
        "checked_epoch": time.time(),
        "status": status,
        "convergence_latest": convergence.get("latest"),
        "warning_count": convergence.get("warning_count"),
        "postprocess_returncode": post_run.returncode,
        "status_returncode": status_run.returncode,
        "convergence_returncode": convergence_run.returncode,
        "vtu_verification": vtu_verification,
        "vtu_verification_error": vtu_error,
    }
    WATCH_JSON.write_text(json.dumps(watch, indent=2))
    return watch


def main() -> None:
    parser = argparse.ArgumentParser(description="Watch the active hifi production solve and verify first VTU.")
    parser.add_argument("--interval-s", type=int, default=300)
    parser.add_argument("--max-polls", type=int, default=0, help="0 means run until interrupted.")
    args = parser.parse_args()

    count = 0
    while args.max_polls <= 0 or count < args.max_polls:
        watch = poll_once()
        latest = watch.get("convergence_latest") or {}
        print(
            time.strftime("%Y-%m-%d %H:%M:%S"),
            f"step={latest.get('step')}",
            f"iteration={latest.get('iteration')}",
            f"vtu={watch.get('status', {}).get('result_vtu_count')}",
            f"free_gib={watch.get('status', {}).get('free_gib')}",
            flush=True,
        )
        count += 1
        if args.max_polls > 0 and count >= args.max_polls:
            break
        time.sleep(args.interval_s)


if __name__ == "__main__":
    main()
