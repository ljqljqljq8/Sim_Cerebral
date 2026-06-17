#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/data_raw/luisi2024"
mkdir -p "$OUT/extracted"

BASE="https://static-content.springer.com/esm/art%3A10.1038%2Fs41598-024-58925-8/MediaObjects"

download_if_missing() {
  local url="$1"
  local out="$2"
  if [[ -s "$out" ]]; then
    echo "exists: $out"
  else
    curl -L --fail "$url" -o "$out"
  fi
}

download_if_missing "$BASE/41598_2024_58925_MOESM1_ESM.pdf" "$OUT/41598_2024_58925_MOESM1_ESM.pdf"
download_if_missing "$BASE/41598_2024_58925_MOESM2_ESM.csv" "$OUT/41598_2024_58925_MOESM2_ESM.csv"
download_if_missing "$BASE/41598_2024_58925_MOESM3_ESM.zip" "$OUT/41598_2024_58925_MOESM3_ESM.zip"

unzip -n "$OUT/41598_2024_58925_MOESM3_ESM.zip" -d "$OUT/extracted"
find "$OUT" -maxdepth 3 -type f | sort

