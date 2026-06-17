from __future__ import annotations

import json
import inspect

from sv import meshing


def public_methods(obj):
    return sorted(name for name in dir(obj) if not name.startswith("_"))


def main() -> None:
    tetgen = meshing.TetGen()
    options = meshing.TetGenOptions(global_edge_size=0.1, surface_mesh_flag=True, volume_mesh_flag=True)
    signatures = {}
    for name in [
        "compute_model_boundary_faces",
        "generate_mesh",
        "set_boundary_layer_options",
        "set_walls",
        "write_mesh",
    ]:
        try:
            signatures[name] = str(inspect.signature(getattr(tetgen, name)))
        except Exception as exc:
            signatures[name] = f"{type(exc).__name__}: {exc}"
    for name in ["local_edge_size", "create_local_edge_size", "get_values"]:
        try:
            signatures[f"options.{name}"] = str(inspect.signature(getattr(options, name)))
        except Exception as exc:
            signatures[f"options.{name}"] = f"{type(exc).__name__}: {exc}"
    docs = {}
    for name in ["set_boundary_layer_options", "create_local_edge_size"]:
        obj = getattr(tetgen if name.startswith("set_") else options, name)
        docs[name] = getattr(obj, "__doc__", None)
    data = {
        "tetgen_methods": public_methods(tetgen),
        "tetgen_options_methods": public_methods(options),
        "signatures": signatures,
        "docs": docs,
        "option_values": options.get_values(),
        "tetgen_type": str(type(tetgen)),
        "tetgen_options_type": str(type(options)),
    }
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
