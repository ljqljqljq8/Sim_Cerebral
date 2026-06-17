from __future__ import annotations

from pathlib import Path
import argparse

import numpy as np
import pandas as pd
import yaml

from utils_units import ml_min_to_cm3_s


ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "cases" / "cow_luisi_mvp"
BC = CASE / "bc"


def inlet_area_cm2(name: str, params: dict) -> tuple[float, str]:
    if params.get("area_cm2") is not None:
        return float(params["area_cm2"]), "area_cm2"
    if params.get("diameter_mm") is not None:
        diameter_cm = float(params["diameter_mm"]) * 0.1
        return np.pi * (diameter_cm / 2.0) ** 2, "diameter_mm"
    raise ValueError(f"{name} needs either diameter_mm or area_cm2.")


def mean_flow_from_ultrasound(name: str, params: dict, area_cm2: float) -> tuple[float, float, str]:
    if params.get("mean_flow_mL_min") is not None:
        qmean = ml_min_to_cm3_s(params["mean_flow_mL_min"])
        return qmean, float(params["mean_flow_mL_min"]), "mean_flow_mL_min"
    if params.get("mean_velocity_cm_s") is not None:
        qmean = float(params["mean_velocity_cm_s"]) * area_cm2
        return qmean, qmean * 60.0, "mean_velocity_cm_s"
    if params.get("mean_velocity_m_s") is not None:
        qmean = float(params["mean_velocity_m_s"]) * 100.0 * area_cm2
        return qmean, qmean * 60.0, "mean_velocity_m_s"
    raise ValueError(
        f"{name} needs mean_flow_mL_min, mean_velocity_cm_s, or mean_velocity_m_s."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate inlet flow files from ultrasound-like inputs.")
    parser.add_argument(
        "--config",
        default=str(ROOT / "config" / "ultrasound_simulation.yaml"),
        help="YAML file containing inlet mean flow or mean velocity inputs.",
    )
    args = parser.parse_args()

    BC.mkdir(parents=True, exist_ok=True)
    cfg = yaml.safe_load(Path(args.config).read_text())
    period = float(cfg["cardiac_period_s"])
    n_points = int(cfg["n_points"])
    fourier_modes = int(cfg["fourier_modes"])
    times = np.linspace(0.0, period, n_points)

    summary_rows = []
    waveform_rows = {"time_s": times}

    for name, params in cfg["inlets"].items():
        area_cm2, area_source = inlet_area_cm2(name, params)
        qmean, mean_flow_mL_min, input_mode = mean_flow_from_ultrasound(name, params, area_cm2)
        pulsatility = float(params.get("pulsatility", 0.45))
        phase = float(params.get("phase_rad", 0.0))
        shape = (
            1.0
            + pulsatility * np.sin(2.0 * np.pi * times / period - phase)
            + 0.18 * pulsatility * np.sin(4.0 * np.pi * times / period - 0.6 - phase)
        )
        shape = np.maximum(shape, 0.05)
        shape = shape / np.trapz(shape, times) * period
        q_cm3_s = qmean * shape
        q_solver = -q_cm3_s

        flow_path = BC / f"{name}.flow"
        with flow_path.open("w") as stream:
            stream.write(f"{n_points} {fourier_modes}\n")
            for t, q in zip(times, q_solver):
                stream.write(f"{t:.8f} {q:.10e}\n")

        waveform_rows[f"{name}_flow_cm3_s"] = q_cm3_s
        waveform_rows[f"{name}_solver_flow_cm3_s"] = q_solver
        waveform_rows[f"{name}_mean_velocity_cm_s"] = q_cm3_s / area_cm2
        summary_rows.append(
            {
                "name": name,
                "input_mode": input_mode,
                "mean_flow_mL_min": mean_flow_mL_min,
                "mean_flow_cm3_s": qmean,
                "diameter_mm_simulated_ultrasound": params.get("diameter_mm"),
                "area_source": area_source,
                "cross_section_area_cm2": area_cm2,
                "mean_velocity_cm_s": qmean / area_cm2,
                "flow_file": str(flow_path.relative_to(ROOT)),
            }
        )

    pd.DataFrame(waveform_rows).to_csv(BC / "simulated_ultrasound_inputs.csv", index=False)
    pd.DataFrame(summary_rows).to_csv(BC / "inlet_summary.csv", index=False)
    print("Wrote flow files to", BC)


if __name__ == "__main__":
    main()
