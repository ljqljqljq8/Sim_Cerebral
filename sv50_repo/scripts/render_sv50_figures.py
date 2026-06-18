#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import pyvista as pv


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASE_DIR = REPO_ROOT / "case" / "sv50"
DEFAULT_OUT_DIR = DEFAULT_CASE_DIR / "reports" / "Figures"


COLORS = {
    "surface": "#B8B8B0",
    "inlet": "#1B8A72",
    "brain_outlet": "#E59A2E",
    "external_outlet": "#7C62D0",
}


@dataclass
class BoundaryFace:
    code: str
    name: str
    role: str
    group: str
    vessel: str
    area_cm2: float
    cell_count: int
    surface_file: str
    centroid: np.ndarray
    mesh: pv.PolyData


def load_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def classify(name: str, role: str) -> tuple[str, str]:
    if role == "inlet":
        return "inlet", "I"
    if role == "wall":
        return "wall", "W"
    if any(token in name for token in ("_ACA_", "_MCA_", "_PCA_")):
        return "brain_outlet", "B"
    return "external_outlet", "E"


def face_sort_key(face: dict) -> tuple[int, str]:
    name = face["name"]
    role = face.get("role", "")
    group, _ = classify(name, role)
    rank = {"inlet": 0, "brain_outlet": 1, "external_outlet": 2, "wall": 3}[group]
    side_rank = 0 if name.startswith("L_") else 1 if name.startswith("R_") else 2
    return rank, f"{side_rank}_{name}"


def load_faces(case_dir: Path) -> list[BoundaryFace]:
    labels_path = case_dir / "simvascular" / "face_labels.json"
    with labels_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    counters = {"I": 0, "B": 0, "E": 0}
    faces: list[BoundaryFace] = []
    for face in sorted(data["faces"], key=face_sort_key):
        name = face["name"]
        role = face.get("role", "")
        group, prefix = classify(name, role)
        if group == "wall":
            continue
        counters[prefix] += 1
        code = f"{prefix}{counters[prefix]}"
        surface_path = case_dir / "simvascular" / "mesh" / "mesh-surfaces" / face["surface_file"]
        centroid = np.asarray(face.get("centroid_cm", pv.read(surface_path).center), dtype=float)
        faces.append(
            BoundaryFace(
                code=code,
                name=name,
                role=role,
                group=group,
                vessel=face.get("vessel") or "",
                area_cm2=float(face.get("area_cm2", 0.0)),
                cell_count=int(face.get("cell_count", 0)),
                surface_file=face["surface_file"],
                centroid=centroid,
                mesh=pv.read(surface_path),
            )
        )
    return faces


def camera_for(mesh: pv.DataSet, view: str) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[int, int, int], float]:
    xmin, xmax, ymin, ymax, zmin, zmax = mesh.bounds
    center = np.asarray(mesh.center)
    span = np.asarray([xmax - xmin, ymax - ymin, zmax - zmin], dtype=float)
    dist = float(max(span) * 3.0)
    if view == "front":
        pos = (center[0], ymin - dist, center[2])
        scale = max(span[0], span[2]) * 0.56
        return pos, tuple(center), (0, 0, 1), scale
    if view == "side":
        pos = (xmax + dist, center[1], center[2])
        scale = max(span[1], span[2]) * 0.56
        return pos, tuple(center), (0, 0, 1), scale
    if view == "top":
        pos = (center[0], center[1], zmax + dist)
        scale = max(span[0], span[1]) * 0.56
        return pos, tuple(center), (0, 1, 0), scale
    if view == "oblique":
        pos = (center[0] - dist * 0.55, center[1] - dist * 0.85, center[2] + dist * 0.45)
        scale = max(span[0], span[1], span[2]) * 0.52
        return pos, tuple(center), (0, 0, 1), scale
    raise ValueError(f"Unknown view: {view}")


def add_scene(
    plotter: pv.Plotter,
    exterior: pv.PolyData,
    faces: list[BoundaryFace],
    view: str,
    labels: bool,
) -> None:
    plotter.set_background("white")
    plotter.add_mesh(
        exterior,
        color=COLORS["surface"],
        opacity=0.28,
        smooth_shading=True,
        specular=0.18,
    )
    for face in faces:
        plotter.add_mesh(
            face.mesh,
            color=COLORS[face.group],
            opacity=1.0,
            show_edges=True,
            edge_color="black",
            line_width=1.0,
            smooth_shading=False,
        )
        marker_radius = max(0.10, min(0.22, (face.area_cm2 / np.pi) ** 0.5 * 0.55))
        marker = pv.Sphere(
            radius=marker_radius,
            center=tuple(face.centroid),
            theta_resolution=18,
            phi_resolution=12,
        )
        plotter.add_mesh(
            marker,
            color=COLORS[face.group],
            opacity=0.92,
            smooth_shading=True,
            specular=0.15,
        )

    if labels:
        for group in ("inlet", "brain_outlet", "external_outlet"):
            group_faces = [face for face in faces if face.group == group]
            if not group_faces:
                continue
            points = np.asarray([face.centroid for face in group_faces])
            texts = [face.code for face in group_faces]
            plotter.add_point_labels(
                points,
                texts,
                font_size=17,
                point_size=7,
                shape_color="white",
                shape_opacity=0.92,
                text_color="black",
                margin=4,
                always_visible=True,
            )

    pos, focal, viewup, scale = camera_for(exterior, view)
    plotter.camera_position = (pos, focal, viewup)
    plotter.camera.parallel_projection = True
    plotter.camera.parallel_scale = scale
    plotter.show_bounds(
        grid="front",
        location="outer",
        ticks="outside",
        color="#9E9E9E",
        font_size=8,
        xtitle="X cm",
        ytitle="Y cm",
        ztitle="Z cm",
    )


def render_panel(exterior: pv.PolyData, faces: list[BoundaryFace], view: str, out: Path, labels: bool) -> None:
    plotter = pv.Plotter(off_screen=True, window_size=(1200, 1200))
    add_scene(plotter, exterior, faces, view, labels)
    plotter.screenshot(str(out))
    plotter.close()


def label_image(path: Path, title: str, legend: bool = False) -> Image.Image:
    img = Image.open(path).convert("RGB")
    top = 74
    bottom = 56 if legend else 20
    canvas = Image.new("RGB", (img.width, img.height + top + bottom), "white")
    canvas.paste(img, (0, top))
    draw = ImageDraw.Draw(canvas)
    title_font = load_font(38)
    small_font = load_font(18)
    draw.text((24, 16), title, fill="#1F1F1F", font=title_font)
    if legend:
        x = 26
        y = canvas.height - 38
        for text, color in [
            ("green = inlet faces", COLORS["inlet"]),
            ("orange = brain outlet faces", COLORS["brain_outlet"]),
            ("purple = STA/ECA outlet faces", COLORS["external_outlet"]),
            ("gray = exterior surface", COLORS["surface"]),
        ]:
            draw.rectangle([x, y + 4, x + 18, y + 22], fill=color, outline="#444444")
            draw.text((x + 26, y), text, fill="#333333", font=small_font)
            x += 270
    return canvas


def combine_three(panel_paths: list[Path], titles: list[str], out: Path) -> None:
    panels = [label_image(path, title, legend=(idx == 0)) for idx, (path, title) in enumerate(zip(panel_paths, titles))]
    height = max(panel.height for panel in panels)
    width = sum(panel.width for panel in panels)
    combined = Image.new("RGB", (width, height), "white")
    x = 0
    for panel in panels:
        combined.paste(panel, (x, 0))
        x += panel.width
    combined.save(out, quality=95)


def write_face_index(faces: list[BoundaryFace], out_csv: Path, out_png: Path) -> None:
    rows = [
        {
            "code": face.code,
            "name": face.name,
            "group": face.group,
            "role": face.role,
            "area_cm2": f"{face.area_cm2:.6f}",
            "cell_count": str(face.cell_count),
            "surface_file": face.surface_file,
            "vessel": face.vessel,
        }
        for face in faces
    ]
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    font = load_font(18)
    bold = load_font(24)
    line_h = 30
    col_x = [22, 88, 220, 510, 1055, 1165, 1260]
    width = 2050
    height = 90 + line_h * (len(rows) + 1)
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    draw.text((22, 18), "sv50 boundary face index", fill="#1F1F1F", font=bold)
    headers = ["code", "group", "role", "name", "area", "cells", "surface_file"]
    y = 62
    draw.rectangle([14, y - 4, width - 14, y + line_h - 2], fill="#F0F0F0")
    for x, header in zip(col_x, headers):
        draw.text((x, y), header, fill="#222222", font=font)
    y += line_h
    for idx, row in enumerate(rows):
        if idx % 2:
            draw.rectangle([14, y - 4, width - 14, y + line_h - 2], fill="#FAFAFA")
        color = COLORS[row["group"]]
        draw.rectangle([22, y + 5, 42, y + 24], fill=color, outline="#444444")
        values = [
            row["code"],
            row["group"].replace("_", " "),
            row["role"],
            row["name"],
            row["area_cm2"],
            row["cell_count"],
            row["surface_file"],
        ]
        for x, value in zip(col_x, values):
            draw.text((x, y), value, fill="#222222", font=font)
        y += line_h
    img.save(out_png, quality=95)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render sv50 mesh and boundary-face figures.")
    parser.add_argument("--case-dir", default=str(DEFAULT_CASE_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--surface", choices=["exterior", "solve"], default="exterior")
    args = parser.parse_args()

    case_dir = Path(args.case_dir).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.surface == "solve":
        exterior_path = case_dir / "geometry" / "surface_solve.vtp"
    else:
        exterior_path = case_dir / "simvascular" / "mesh" / "mesh-complete.exterior.vtp"
    exterior = pv.read(exterior_path).extract_surface()
    faces = load_faces(case_dir)

    panel_specs = [
        ("front", "Front / X-Z"),
        ("side", "Side / Y-Z"),
        ("top", "Top / X-Y"),
    ]
    panel_paths = []
    for view, _ in panel_specs:
        panel_path = out_dir / f"sv50_panel_{view}_grouped_caps.png"
        render_panel(exterior, faces, view, panel_path, labels=True)
        panel_paths.append(panel_path)

    combine_three(
        panel_paths,
        [title for _, title in panel_specs],
        out_dir / "sv50_mesh_overview_grouped_caps.png",
    )
    oblique = out_dir / "sv50_oblique_numbered_caps.png"
    render_panel(exterior, faces, "oblique", oblique, labels=True)
    label_image(oblique, "Oblique / numbered caps", legend=True).save(
        out_dir / "sv50_oblique_numbered_caps_annotated.png",
        quality=95,
    )
    render_panel(exterior, faces, "front", out_dir / "sv50_front_grouped_caps_no_labels.png", labels=False)

    write_face_index(
        faces,
        out_dir / "sv50_boundary_face_index.csv",
        out_dir / "sv50_boundary_face_index.png",
    )
    print(f"wrote figures to {out_dir}")
    print(f"boundary faces: {len(faces)} terminal caps plus exterior surface")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
