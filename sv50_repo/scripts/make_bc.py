#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
from pathlib import Path

from common import REPO_ROOT, load_yaml, mmhg_to_barye, ml_min_to_cm3_s, read_json, resolve, waveform_scale, write_csv, write_json


def write_flow(path: Path, mean_ml_min: float, cycle_s: float, dt: float, waveform_cfg: dict, modes: int) -> None:
    steps = int(round(cycle_s / dt))
    rows = []
    for i in range(steps + 1):
        t = min(cycle_s, i * dt)
        scale = waveform_scale(
            t,
            cycle_s,
            float(waveform_cfg.get("systolic_fraction", 0.3)),
            float(waveform_cfg.get("second_harmonic_fraction", 0.06)),
            float(waveform_cfg.get("phase_s", 0.0)),
        )
        rows.append((t, ml_min_to_cm3_s(mean_ml_min) * scale))

    mean_scale = sum(q for _, q in rows[:-1]) / max(len(rows) - 1, 1) / ml_min_to_cm3_s(mean_ml_min)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(f"{len(rows)}    {int(modes)}\n")
        for t, q in rows:
            normalized_q = q / mean_scale
            f.write(f"{t:.8f} {-abs(normalized_q):.8f}\n")


def repo_rel(path: Path) -> str:
    return str(path.resolve().relative_to(REPO_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate sv50 inflow files and RCR outlet table.")
    parser.add_argument("--case-dir", default="case/sv50")
    parser.add_argument("--bc-config", default="configs/bc.yaml")
    args = parser.parse_args()

    case_dir = resolve(args.case_dir)
    bc_cfg = load_yaml(args.bc_config)
    terminal_planes = read_json(case_dir / "geometry" / "terminal_planes.json")["terminal_planes"]
    terminal_names = {item["name"] for item in terminal_planes}

    truth = bc_cfg["truth_bc"]
    inlets = {k: float(v) for k, v in truth["inlet_mean_flows_ml_min"].items()}
    outlets = {k: float(v) for k, v in truth["outlet_target_flows_ml_min"].items()}
    missing = sorted((set(inlets) | set(outlets)) - terminal_names)
    if missing:
        raise SystemExit("BC names not found in terminal planes: " + ", ".join(missing))
    inlet_sum = sum(inlets.values())
    outlet_sum = sum(outlets.values())
    if not math.isclose(inlet_sum, outlet_sum, rel_tol=0.0, abs_tol=1e-6):
        raise SystemExit(f"Inlet/outlet flow mismatch: {inlet_sum} vs {outlet_sum} ml/min")

    sim_dir = case_dir / "simulation_truth"
    cycle_s = float(truth["cardiac_cycle_s"])
    dt = float(truth.get("sample_dt_s", 0.01))
    waveform = bc_cfg.get("waveform", {})
    modes = int(waveform.get("fourier_modes", 16))
    inlet_files = {}
    for inlet, mean in inlets.items():
        wf = waveform.get("vertebral" if "_VA_" in inlet else "carotid", {})
        flow_path = sim_dir / f"inlet_{inlet}.flow"
        write_flow(flow_path, mean, cycle_s, dt, wf, modes)
        inlet_files[inlet] = repo_rel(flow_path)

    pressure = truth["pressure"]
    dp = mmhg_to_barye(float(pressure["target_mean_mmHg"]) - float(pressure["venous_or_distal_mmHg"]))
    prox = float(bc_cfg["rcr"].get("proximal_fraction", 0.05))
    c_total = float(bc_cfg["rcr"].get("total_compliance_cm3_per_barye", 1.9e-5))
    rows = []
    for outlet, target_ml_min in outlets.items():
        resistance = dp / ml_min_to_cm3_s(target_ml_min)
        rows.append(
            {
                "outlet": outlet,
                "target_flow_ml_min": f"{target_ml_min:.9g}",
                "Rp_barye_s_per_cm3": f"{prox * resistance:.9g}",
                "C_cm3_per_barye": f"{c_total * target_ml_min / outlet_sum:.9g}",
                "Rd_barye_s_per_cm3": f"{(1.0 - prox) * resistance:.9g}",
            }
        )
    write_csv(sim_dir / "outlet_rcr.csv", rows)
    summary = {
        "case": repo_rel(case_dir),
        "cardiac_cycle_s": cycle_s,
        "inlet_mean_flows_ml_min": inlets,
        "outlet_target_flows_ml_min": outlets,
        "inlet_total_ml_min": inlet_sum,
        "outlet_total_ml_min": outlet_sum,
        "pressure": pressure,
        "inlet_flow_files": inlet_files,
        "outlet_rcr_csv": repo_rel(sim_dir / "outlet_rcr.csv"),
        "notes": bc_cfg.get("notes", []),
    }
    write_json(sim_dir / "bc_summary.json", summary)
    print(f"wrote {sim_dir / 'bc_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
