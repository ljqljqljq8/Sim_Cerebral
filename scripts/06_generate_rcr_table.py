from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from utils_units import capacitance_ml_mmhg_to_cgs, mmhg_to_dyn_cm2, resistance_mmhg_s_ml_to_cgs


ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "cases" / "cow_luisi_mvp"
BC = CASE / "bc"


def main() -> None:
    BC.mkdir(parents=True, exist_ok=True)
    cfg = yaml.safe_load((ROOT / "config" / "rcr_luisi_wm.yaml").read_text())
    alpha = float(cfg["proximal_resistance_fraction"])
    initial_pressure = mmhg_to_dyn_cm2(cfg["initial_pressure_mmhg"])
    distal_pressure = mmhg_to_dyn_cm2(cfg["distal_pressure_mmhg"])

    rows = []
    for name, params in cfg["outlets"].items():
        total_r = resistance_mmhg_s_ml_to_cgs(params["total_resistance_mmhg_s_ml"])
        rows.append(
            {
                "face": name,
                "group": params["group"],
                "Rp_dyn_s_cm5": alpha * total_r,
                "Rd_dyn_s_cm5": (1.0 - alpha) * total_r,
                "C_cm5_dyn": capacitance_ml_mmhg_to_cgs(params["capacitance_ml_mmhg"]),
                "Distal_pressure_dyn_cm2": distal_pressure,
                "Initial_pressure_dyn_cm2": initial_pressure,
                "R_total_mmHg_s_mL": float(params["total_resistance_mmhg_s_ml"]),
                "C_mL_mmHg": float(params["capacitance_ml_mmhg"]),
            }
        )

    df = pd.DataFrame(rows)
    df.to_csv(BC / "rcr_values.csv", index=False)
    df[["face", "group", "R_total_mmHg_s_mL", "C_mL_mmHg"]].to_csv(BC / "outlet_targets.csv", index=False)
    print("Wrote", BC / "rcr_values.csv")


if __name__ == "__main__":
    main()

