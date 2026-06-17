from __future__ import annotations

from pathlib import Path
import argparse
import json
import re
import shutil
import subprocess
import time


ROOT = Path(__file__).resolve().parents[1]
SOLVER_DIR = ROOT / "cases" / "cow_luisi_mvp" / "solver"
DEFAULT_RUN_LOG = SOLVER_DIR / "solver_production_save20_np7.run.log"
DEFAULT_MONITOR_LOG = SOLVER_DIR / "monitor_disk_production_save20.log"
DEFAULT_OUTPUT_DIR = SOLVER_DIR / "7-procs"
DEFAULT_STATUS_OUT = SOLVER_DIR / "solver_production_save20_np7.progress.json"


NS_RE = re.compile(r"NS\s+(\d+)-(\d+)(s?)\s+")


def parse_latest_ns(log_path: Path) -> dict[str, object] | None:
    if not log_path.exists():
        return None
    latest = None
    for line in log_path.read_text(errors="replace").splitlines():
        match = NS_RE.search(line)
        if not match:
            continue
        latest = {
            "step": int(match.group(1)),
            "iteration": int(match.group(2)),
            "converged_marker": bool(match.group(3)),
            "line": line.strip(),
        }
    return latest


def resolve(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def process_snapshot(solver_xml: str | None) -> list[str]:
    completed = subprocess.run(
        ["ps", "-o", "pid,ppid,etime,%cpu,%mem,command", "-ax"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    needles = ["solver_production"]
    if solver_xml:
        needles.extend({solver_xml, Path(solver_xml).name})
    return [
        line
        for line in completed.stdout.splitlines()
        if any(needle in line for needle in needles) or "monitor_disk_production_save20.py" in line
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-log", default=str(DEFAULT_RUN_LOG.relative_to(ROOT)))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR.relative_to(ROOT)))
    parser.add_argument("--monitor-log", default=str(DEFAULT_MONITOR_LOG.relative_to(ROOT)))
    parser.add_argument("--status-out", default=str(DEFAULT_STATUS_OUT.relative_to(ROOT)))
    parser.add_argument("--solver-xml", default="solver_production_save20.xml")
    args = parser.parse_args()

    run_log = resolve(args.run_log)
    output_dir = resolve(args.output_dir)
    monitor_log = resolve(args.monitor_log)
    status_out = resolve(args.status_out)

    vtus = sorted(output_dir.glob("result_*.vtu"))
    disk = shutil.disk_usage(ROOT)
    status = {
        "checked_epoch": time.time(),
        "latest_ns": parse_latest_ns(run_log),
        "result_vtu_count": len(vtus),
        "latest_vtu": str(vtus[-1].relative_to(ROOT)) if vtus else None,
        "output_dir": str(output_dir.relative_to(ROOT)),
        "output_dir_bytes": sum(path.stat().st_size for path in output_dir.glob("*") if path.is_file())
        if output_dir.exists()
        else 0,
        "free_gib": disk.free / 1024**3,
        "stop_sim_exists": (SOLVER_DIR / "STOP_SIM").exists(),
        "processes": process_snapshot(args.solver_xml),
        "run_log": str(run_log.relative_to(ROOT)),
        "monitor_log": str(monitor_log.relative_to(ROOT)),
    }
    status_out.write_text(json.dumps(status, indent=2))
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
