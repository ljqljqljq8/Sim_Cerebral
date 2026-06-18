from __future__ import annotations

import csv
import json
import math
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else (REPO_ROOT / p).resolve()


def load_yaml(path: str | Path) -> dict[str, Any]:
    with resolve(path).open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def write_yaml(path: str | Path, data: dict[str, Any]) -> None:
    p = resolve(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)


def read_json(path: str | Path) -> Any:
    with resolve(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str | Path, data: Any) -> None:
    p = resolve(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def write_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    p = resolve(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with p.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with resolve(path).open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def copy_file(src: str | Path, dst: str | Path) -> None:
    s = resolve(src)
    d = resolve(dst)
    if not s.exists():
        raise FileNotFoundError(s)
    d.parent.mkdir(parents=True, exist_ok=True)
    if s.resolve() == d.resolve():
        return
    shutil.copy2(s, d)


def find_executable(candidates: list[str | Path | None]) -> Path | None:
    for candidate in candidates:
        if not candidate:
            continue
        text = str(candidate)
        if os.sep in text:
            p = Path(text)
            if p.exists() and os.access(p, os.X_OK):
                return p
        else:
            found = shutil.which(text)
            if found:
                return Path(found)
    return None


def run(cmd: list[str], cwd: Path | None = None) -> int:
    print("+ " + " ".join(cmd))
    return subprocess.run(cmd, cwd=str(cwd or REPO_ROOT)).returncode


def mmhg_to_barye(value: float) -> float:
    return value * 1333.22


def ml_min_to_cm3_s(value: float) -> float:
    return value / 60.0


def waveform_scale(t: float, cycle_s: float, systolic_fraction: float, second_harmonic_fraction: float, phase_s: float) -> float:
    x = 2.0 * math.pi * ((t - phase_s) % cycle_s) / cycle_s
    value = 1.0 + systolic_fraction * math.sin(x) + second_harmonic_fraction * math.sin(2.0 * x - 0.7)
    return max(0.15, value)
