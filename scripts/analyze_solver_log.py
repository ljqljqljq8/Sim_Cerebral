from __future__ import annotations

from pathlib import Path
import argparse
import json
import re


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG = ROOT / "cases" / "cow_luisi_mvp" / "solver" / "solver_production_save20_np7.run.log"

NS_RE = re.compile(
    r"NS\s+(?P<step>\d+)-(?P<iteration>\d+)(?P<marker>s?)\s+"
    r"(?P<time>[0-9.eE+-]+)\s+"
    r"\[(?P<db>[-0-9]+)\s+"
    r"(?P<ri_r1>[0-9.eE+-]+)\s+"
    r"(?P<ri_r0>[0-9.eE+-]+)\s+"
    r"(?P<r_ri>[0-9.eE+-]+)\]"
)


def parse_log(path: Path) -> dict[str, object]:
    entries = []
    warning_count = 0
    for line in path.read_text(errors="replace").splitlines():
        if "WARNING: The linear system solution has not converged" in line:
            warning_count += 1
        match = NS_RE.search(line)
        if not match:
            continue
        entries.append(
            {
                "step": int(match.group("step")),
                "iteration": int(match.group("iteration")),
                "converged_marker": bool(match.group("marker")),
                "time": float(match.group("time")),
                "db": int(match.group("db")),
                "ri_r1": float(match.group("ri_r1")),
                "ri_r0": float(match.group("ri_r0")),
                "r_ri": float(match.group("r_ri")),
                "warning": "WARNING:" in line,
                "line": line.strip(),
            }
        )

    by_step: dict[int, list[dict[str, object]]] = {}
    for entry in entries:
        by_step.setdefault(int(entry["step"]), []).append(entry)

    step_summary = []
    for step, step_entries in sorted(by_step.items()):
        last = step_entries[-1]
        step_summary.append(
            {
                "step": step,
                "iterations_observed": len(step_entries),
                "last_iteration": last["iteration"],
                "last_ri_r1": last["ri_r1"],
                "last_ri_r0": last["ri_r0"],
                "last_r_ri": last["r_ri"],
                "has_converged_marker": any(bool(entry["converged_marker"]) for entry in step_entries),
                "warning_iterations": sum(1 for entry in step_entries if entry["warning"]),
            }
        )

    latest = entries[-1] if entries else None
    return {
        "log": str(path.relative_to(ROOT)),
        "entry_count": len(entries),
        "warning_count": warning_count,
        "latest": latest,
        "completed_or_started_steps": sorted(by_step),
        "step_summary": step_summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", default=str(DEFAULT_LOG), help="svMultiPhysics run log to analyze.")
    parser.add_argument("--output", default=None, help="Optional JSON output path.")
    args = parser.parse_args()

    path = Path(args.log)
    if not path.is_absolute():
        path = ROOT / path
    result = parse_log(path)
    text = json.dumps(result, indent=2)
    print(text)
    if args.output:
        out = Path(args.output)
        if not out.is_absolute():
            out = ROOT / out
        out.write_text(text)


if __name__ == "__main__":
    main()
