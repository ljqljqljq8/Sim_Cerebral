from __future__ import annotations

import json
import sys

import sv


def main() -> None:
    from sv import meshing

    payload = {
        "python": sys.executable,
        "sv_module": str(sv),
        "has_meshing": hasattr(sv, "meshing"),
        "has_tetgen": hasattr(meshing, "TetGen"),
        "has_tetgen_options": hasattr(meshing, "TetGenOptions"),
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

