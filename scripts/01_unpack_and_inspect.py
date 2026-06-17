from __future__ import annotations

from pathlib import Path
import json
import zipfile

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data_raw" / "luisi2024"
ZIP_FILE = RAW / "41598_2024_58925_MOESM3_ESM.zip"
CSV_FILE = RAW / "41598_2024_58925_MOESM2_ESM.csv"
OUT = RAW / "extracted"


def extract_without_overwrite(zip_file: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_file, "r") as archive:
        for member in archive.infolist():
            target = out_dir / member.filename
            if target.exists():
                continue
            archive.extract(member, out_dir)


def main() -> None:
    if not ZIP_FILE.exists():
        raise FileNotFoundError(f"Missing {ZIP_FILE}. Run scripts/00_download_luisi.sh first.")
    if not CSV_FILE.exists():
        raise FileNotFoundError(f"Missing {CSV_FILE}. Run scripts/00_download_luisi.sh first.")

    extract_without_overwrite(ZIP_FILE, OUT)
    stls = sorted(OUT.rglob("*.stl"))
    df = pd.read_csv(CSV_FILE)

    summary = {
        "zip_file": str(ZIP_FILE.relative_to(ROOT)),
        "csv_file": str(CSV_FILE.relative_to(ROOT)),
        "stl_files": [str(p.relative_to(ROOT)) for p in stls],
        "csv_shape": list(df.shape),
        "csv_columns": list(df.columns),
        "csv_head": df.head(5).to_dict(orient="records"),
    }
    summary_path = RAW / "inspection_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))

    print("STL files:")
    for path in stls:
        print(f" - {path.relative_to(ROOT)}")
    print("\nCSV shape:", df.shape)
    print("CSV columns:", list(df.columns))
    print("Wrote", summary_path.relative_to(ROOT))


if __name__ == "__main__":
    main()

