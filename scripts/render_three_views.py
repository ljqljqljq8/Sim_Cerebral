from __future__ import annotations

from pathlib import Path

import pyvista as pv


ROOT = Path(__file__).resolve().parents[1]
CASE_DIR = ROOT / "cases" / "cow_luisi_mvp"
MESH_DIR = CASE_DIR / "mesh"
SURF_DIR = MESH_DIR / "mesh-surfaces"
OUT_DIR = CASE_DIR / "results" / "visualization"


INLETS = ["LICA", "RICA", "LVA", "RVA"]
OUTLETS = ["LACA", "RACA", "LMCA", "RMCA", "LPCA", "RPCA"]


def add_vessel(plotter: pv.Plotter) -> None:
    exterior = pv.read(MESH_DIR / "mesh-complete.exterior.vtp").clean()
    plotter.add_mesh(
        exterior,
        color="#d6d9dc",
        smooth_shading=True,
        specular=0.25,
        specular_power=20,
    )

    for name in INLETS:
        path = SURF_DIR / f"{name}.vtp"
        if path.exists():
            plotter.add_mesh(pv.read(path), color="#d84a3a", smooth_shading=True)

    for name in OUTLETS:
        path = SURF_DIR / f"{name}.vtp"
        if path.exists():
            plotter.add_mesh(pv.read(path), color="#2f73d9", smooth_shading=True)


def setup_camera(plotter: pv.Plotter, view: str, zoom: float) -> None:
    if view == "front":
        plotter.view_xz()
    elif view == "side":
        plotter.view_yz()
    elif view == "top":
        plotter.view_xy()
    else:
        raise ValueError(view)
    plotter.camera.parallel_projection = True
    plotter.camera.zoom(zoom)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUT_DIR / "vessel_three_views.png"

    pv.global_theme.background = "white"
    plotter = pv.Plotter(off_screen=True, shape=(1, 3), window_size=(2400, 850), border=False)

    views = [
        ("front", "Front / X-Z", 1.02),
        ("side", "Side / Y-Z", 1.02),
        ("top", "Top / X-Y", 1.85),
    ]
    for idx, (view, title, zoom) in enumerate(views):
        plotter.subplot(0, idx)
        add_vessel(plotter)
        plotter.add_text(title, font_size=14, color="black", position="upper_left")
        plotter.add_text("red=inlets  blue=outlets", font_size=9, color="#333333", position="lower_left")
        plotter.show_bounds(
            grid="front",
            location="outer",
            all_edges=False,
            font_size=8,
            color="#666666",
            xtitle="X cm",
            ytitle="Y cm",
            ztitle="Z cm",
        )
        setup_camera(plotter, view, zoom)

    plotter.screenshot(str(output))
    plotter.close()
    print(output)


if __name__ == "__main__":
    main()
