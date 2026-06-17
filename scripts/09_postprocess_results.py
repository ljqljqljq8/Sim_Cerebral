from __future__ import annotations

from pathlib import Path
import argparse
import json
import math
import re

import numpy as np
import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "cases" / "cow_luisi_mvp"


NUMERIC_LINE = re.compile(r"^[\s+\-0-9.eE]+$")


def read_numeric_table(path: Path) -> pd.DataFrame:
    rows = []
    for line in path.read_text(errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or not NUMERIC_LINE.match(stripped):
            continue
        try:
            rows.append([float(token) for token in stripped.split()])
        except ValueError:
            continue
    if not rows:
        return pd.DataFrame()
    width = max(len(row) for row in rows)
    rows = [row for row in rows if len(row) == width]
    return pd.DataFrame(rows)


def find_output_dir() -> Path | None:
    solver = CASE / "solver"
    candidates = sorted(solver.glob("*-procs"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return candidates[0] if candidates else None


def resolve(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def label_boundary_columns(df: pd.DataFrame, faces: list[str]) -> pd.DataFrame:
    if df.empty:
        return df
    if df.shape[1] == len(faces) + 2:
        df = df.copy()
        df.columns = ["step", "time_s", *faces]
        return df
    if df.shape[1] == len(faces) + 1:
        df = df.copy()
        df.columns = ["time_s", *faces]
        return df
    if df.shape[1] == len(faces):
        df = df.copy()
        df.columns = faces
        df.insert(0, "time_s", np.arange(len(df), dtype=float))
        return df
    df = df.copy()
    df.columns = [f"c{i}" for i in range(df.shape[1])]
    return df


def summarize_boundary_table(df: pd.DataFrame, faces: list[str], period: float) -> pd.DataFrame:
    if df.empty or "time_s" not in df.columns:
        return pd.DataFrame()
    face_cols = [face for face in faces if face in df.columns]
    if not face_cols:
        return pd.DataFrame()
    max_time = float(df["time_s"].max())
    last = df[df["time_s"] >= max_time - period].copy()
    rows = []
    for face in face_cols:
        values = last[face].astype(float)
        rows.append(
            {
                "face": face,
                "mean": values.mean(),
                "min": values.min(),
                "max": values.max(),
                "abs_peak": values.abs().max(),
            }
        )
    return pd.DataFrame(rows)


def write_table_outputs(out_dir: Path, name: str, df: pd.DataFrame, summary: pd.DataFrame) -> None:
    if not df.empty:
        df.to_csv(out_dir / f"{name}_timeseries.csv", index=False)
    if not summary.empty:
        summary.to_csv(out_dir / f"{name}_summary.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Postprocess svMultiPhysics boundary and VTK outputs.")
    parser.add_argument(
        "--solver-output-dir",
        default=None,
        help="Explicit solver output directory, for example cases/cow_luisi_mvp/solver/6-procs.",
    )
    parser.add_argument(
        "--post-dir",
        default=str(CASE / "results" / "post"),
        help="Directory for postprocessed CSV/status outputs.",
    )
    args = parser.parse_args()

    cfg = yaml.safe_load((ROOT / "config" / "case_luisi.yaml").read_text())
    period = float(cfg["simulation"]["cardiac_period_s"])
    faces = list(cfg["faces"]["inlets"]) + list(cfg["faces"]["outlets"]) + [cfg["faces"]["wall"]]
    outlets = list(cfg["faces"]["outlets"])
    out_dir = resolve(args.post_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    solver_out = resolve(args.solver_output_dir) if args.solver_output_dir else find_output_dir()
    status = {
        "solver_output_dir": str(solver_out.relative_to(ROOT)) if solver_out else None,
        "files_processed": [],
        "missing_files": [],
    }
    if solver_out is None:
        status["missing_files"].append("solver/*-procs")
        (out_dir / "postprocess_status.json").write_text(json.dumps(status, indent=2))
        print("No solver output directory found. Wrote postprocess status only.")
        return

    for stem, filename in {
        "face_flow": "B_NS_Velocity_flux.txt",
        "pressure": "B_NS_Pressure_average.txt",
        "wss": "B_NS_WSS_average.txt",
    }.items():
        path = solver_out / filename
        if not path.exists():
            status["missing_files"].append(str(path.relative_to(ROOT)))
            continue
        raw = read_numeric_table(path)
        labeled = label_boundary_columns(raw, faces)
        summary = summarize_boundary_table(labeled, faces, period)
        write_table_outputs(out_dir, stem, labeled, summary)
        status["files_processed"].append(str(path.relative_to(ROOT)))

        if stem == "face_flow" and not summary.empty:
            outlet_summary = summary[summary["face"].isin(outlets)].copy()
            total = outlet_summary["mean"].sum()
            if math.isfinite(total) and abs(total) > 1.0e-12:
                outlet_summary["flow_split"] = outlet_summary["mean"] / total
                outlet_summary.to_csv(out_dir / "flow_split_last_cycle.csv", index=False)

    vtu_files = sorted(solver_out.glob("result*.vtu"))
    status["vtu_result_count"] = len(vtu_files)
    status["first_vtu"] = str(vtu_files[0].relative_to(ROOT)) if vtu_files else None
    status["last_vtu"] = str(vtu_files[-1].relative_to(ROOT)) if vtu_files else None
    (out_dir / "postprocess_status.json").write_text(json.dumps(status, indent=2))
    print("Wrote postprocess outputs to", out_dir.relative_to(ROOT))


if __name__ == "__main__":
    main()
