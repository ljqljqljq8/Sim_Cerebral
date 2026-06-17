from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
from typing import Iterable

import vtk


@dataclass
class SurfaceRegion:
    region_id: int
    polydata: vtk.vtkPolyData
    area: float
    centroid: tuple[float, float, float]
    normal: tuple[float, float, float]
    bounds: tuple[float, float, float, float, float, float]


def read_polydata(path: str | Path) -> vtk.vtkPolyData:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".stl":
        reader = vtk.vtkSTLReader()
    elif suffix == ".vtp":
        reader = vtk.vtkXMLPolyDataReader()
    elif suffix == ".vtk":
        reader = vtk.vtkPolyDataReader()
    else:
        raise ValueError(f"Unsupported polydata extension: {path}")
    reader.SetFileName(str(path))
    reader.Update()
    return reader.GetOutput()


def write_polydata(polydata: vtk.vtkPolyData, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    if suffix == ".vtp":
        writer = vtk.vtkXMLPolyDataWriter()
    elif suffix == ".stl":
        writer = vtk.vtkSTLWriter()
    elif suffix == ".vtk":
        writer = vtk.vtkPolyDataWriter()
    else:
        raise ValueError(f"Unsupported polydata extension: {path}")
    writer.SetFileName(str(path))
    writer.SetInputData(polydata)
    if writer.Write() != 1:
        raise RuntimeError(f"Failed to write {path}")


def triangulate(polydata: vtk.vtkPolyData) -> vtk.vtkPolyData:
    filt = vtk.vtkTriangleFilter()
    filt.SetInputData(polydata)
    filt.Update()
    return filt.GetOutput()


def clean_polydata(polydata: vtk.vtkPolyData) -> vtk.vtkPolyData:
    filt = vtk.vtkCleanPolyData()
    filt.SetInputData(polydata)
    filt.Update()
    return filt.GetOutput()


def prepare_polydata(polydata: vtk.vtkPolyData) -> vtk.vtkPolyData:
    return clean_polydata(triangulate(polydata))


def scale_polydata(polydata: vtk.vtkPolyData, scale: float) -> vtk.vtkPolyData:
    transform = vtk.vtkTransform()
    transform.Scale(scale, scale, scale)
    filt = vtk.vtkTransformPolyDataFilter()
    filt.SetInputData(polydata)
    filt.SetTransform(transform)
    filt.Update()
    return clean_polydata(filt.GetOutput())


def append_polydata(items: Iterable[vtk.vtkPolyData]) -> vtk.vtkPolyData:
    append = vtk.vtkAppendPolyData()
    for item in items:
        append.AddInputData(item)
    append.Update()
    return clean_polydata(append.GetOutput())


def surface_area(polydata: vtk.vtkPolyData) -> float:
    tri = triangulate(polydata)
    mass = vtk.vtkMassProperties()
    mass.SetInputData(tri)
    mass.Update()
    return float(mass.GetSurfaceArea())


def used_point_ids(polydata: vtk.vtkPolyData) -> set[int]:
    ids = set()
    cell_ids = vtk.vtkIdList()
    for cell_id in range(polydata.GetNumberOfCells()):
        polydata.GetCellPoints(cell_id, cell_ids)
        for idx in range(cell_ids.GetNumberOfIds()):
            ids.add(cell_ids.GetId(idx))
    return ids


def centroid(polydata: vtk.vtkPolyData) -> tuple[float, float, float]:
    ids = used_point_ids(polydata)
    if not ids:
        return (0.0, 0.0, 0.0)
    pts = polydata.GetPoints()
    acc = [0.0, 0.0, 0.0]
    for pid in ids:
        p = pts.GetPoint(pid)
        acc[0] += p[0]
        acc[1] += p[1]
        acc[2] += p[2]
    n = float(len(ids))
    return (acc[0] / n, acc[1] / n, acc[2] / n)


def average_cell_normal(polydata: vtk.vtkPolyData) -> tuple[float, float, float]:
    pts = polydata.GetPoints()
    cell_ids = vtk.vtkIdList()
    acc = [0.0, 0.0, 0.0]
    for cell_id in range(polydata.GetNumberOfCells()):
        polydata.GetCellPoints(cell_id, cell_ids)
        if cell_ids.GetNumberOfIds() < 3:
            continue
        p0 = pts.GetPoint(cell_ids.GetId(0))
        p1 = pts.GetPoint(cell_ids.GetId(1))
        p2 = pts.GetPoint(cell_ids.GetId(2))
        v1 = [p1[i] - p0[i] for i in range(3)]
        v2 = [p2[i] - p0[i] for i in range(3)]
        cross = [
            v1[1] * v2[2] - v1[2] * v2[1],
            v1[2] * v2[0] - v1[0] * v2[2],
            v1[0] * v2[1] - v1[1] * v2[0],
        ]
        acc[0] += cross[0]
        acc[1] += cross[1]
        acc[2] += cross[2]
    mag = math.sqrt(sum(v * v for v in acc))
    if mag == 0.0:
        return (0.0, 0.0, 0.0)
    return (acc[0] / mag, acc[1] / mag, acc[2] / mag)


def count_boundary_edges(polydata: vtk.vtkPolyData) -> int:
    feature = vtk.vtkFeatureEdges()
    feature.SetInputData(polydata)
    feature.BoundaryEdgesOn()
    feature.FeatureEdgesOff()
    feature.ManifoldEdgesOff()
    feature.NonManifoldEdgesOff()
    feature.Update()
    return int(feature.GetOutput().GetNumberOfCells())


def boundary_edge_polydata(polydata: vtk.vtkPolyData) -> vtk.vtkPolyData:
    feature = vtk.vtkFeatureEdges()
    feature.SetInputData(polydata)
    feature.BoundaryEdgesOn()
    feature.FeatureEdgesOff()
    feature.ManifoldEdgesOff()
    feature.NonManifoldEdgesOff()
    feature.Update()
    return clean_polydata(feature.GetOutput())


def _component_nodes(edges: list[tuple[int, int]]) -> list[set[int]]:
    adjacency: dict[int, set[int]] = {}
    for a, b in edges:
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)
    seen: set[int] = set()
    components: list[set[int]] = []
    for node in adjacency:
        if node in seen:
            continue
        stack = [node]
        comp: set[int] = set()
        seen.add(node)
        while stack:
            cur = stack.pop()
            comp.add(cur)
            for nxt in adjacency[cur]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        components.append(comp)
    return components


def _order_loop(nodes: set[int], edges: list[tuple[int, int]]) -> list[int]:
    adjacency = {node: [] for node in nodes}
    for a, b in edges:
        if a in nodes and b in nodes:
            adjacency[a].append(b)
            adjacency[b].append(a)
    start = min(nodes)
    ordered = [start]
    previous = None
    current = start
    for _ in range(len(nodes) + 2):
        candidates = sorted(n for n in adjacency[current] if n != previous)
        if not candidates:
            break
        nxt = candidates[0]
        if nxt == start:
            break
        ordered.append(nxt)
        previous, current = current, nxt
        if len(ordered) == len(nodes):
            break
    return ordered


def boundary_loops(polydata: vtk.vtkPolyData) -> list[list[tuple[float, float, float]]]:
    edges_pd = boundary_edge_polydata(polydata)
    edges: list[tuple[int, int]] = []
    ids = vtk.vtkIdList()
    for cell_id in range(edges_pd.GetNumberOfCells()):
        edges_pd.GetCellPoints(cell_id, ids)
        if ids.GetNumberOfIds() < 2:
            continue
        for i in range(ids.GetNumberOfIds() - 1):
            a = ids.GetId(i)
            b = ids.GetId(i + 1)
            if a != b:
                edges.append((a, b))
    loops = []
    points = edges_pd.GetPoints()
    for nodes in _component_nodes(edges):
        ordered_ids = _order_loop(nodes, edges)
        if len(ordered_ids) >= 3:
            loops.append([points.GetPoint(pid) for pid in ordered_ids])
    return loops


def polygon_centroid(points: list[tuple[float, float, float]]) -> tuple[float, float, float]:
    n = float(len(points))
    return (
        sum(p[0] for p in points) / n,
        sum(p[1] for p in points) / n,
        sum(p[2] for p in points) / n,
    )


def polygon_normal_and_area(points: list[tuple[float, float, float]]) -> tuple[tuple[float, float, float], float]:
    nx = ny = nz = 0.0
    n = len(points)
    for i, p in enumerate(points):
        q = points[(i + 1) % n]
        nx += (p[1] - q[1]) * (p[2] + q[2])
        ny += (p[2] - q[2]) * (p[0] + q[0])
        nz += (p[0] - q[0]) * (p[1] + q[1])
    mag = math.sqrt(nx * nx + ny * ny + nz * nz)
    if mag == 0.0:
        return (0.0, 0.0, 0.0), 0.0
    return (nx / mag, ny / mag, nz / mag), 0.5 * mag


def make_triangle_fan_cap(points: list[tuple[float, float, float]]) -> vtk.vtkPolyData:
    vtk_points = vtk.vtkPoints()
    for p in points:
        vtk_points.InsertNextPoint(p)
    center = polygon_centroid(points)
    center_id = vtk_points.InsertNextPoint(center)
    cells = vtk.vtkCellArray()
    n = len(points)
    for i in range(n):
        tri = vtk.vtkTriangle()
        tri.GetPointIds().SetId(0, center_id)
        tri.GetPointIds().SetId(1, i)
        tri.GetPointIds().SetId(2, (i + 1) % n)
        cells.InsertNextCell(tri)
    polydata = vtk.vtkPolyData()
    polydata.SetPoints(vtk_points)
    polydata.SetPolys(cells)
    return clean_polydata(polydata)


def split_regions_by_feature_angle(polydata: vtk.vtkPolyData, feature_angle: float) -> list[SurfaceRegion]:
    normals = vtk.vtkPolyDataNormals()
    normals.SetInputData(polydata)
    normals.SetFeatureAngle(float(feature_angle))
    normals.SplittingOn()
    normals.ConsistencyOn()
    normals.AutoOrientNormalsOn()
    normals.Update()
    split = normals.GetOutput()

    conn = vtk.vtkConnectivityFilter()
    conn.SetInputData(split)
    conn.SetExtractionModeToAllRegions()
    conn.Update()
    n_regions = conn.GetNumberOfExtractedRegions()

    regions = []
    for region_id in range(n_regions):
        extract = vtk.vtkConnectivityFilter()
        extract.SetInputData(split)
        extract.SetExtractionModeToSpecifiedRegions()
        extract.AddSpecifiedRegion(region_id)
        extract.Update()
        pd = clean_polydata(extract.GetOutput())
        regions.append(
            SurfaceRegion(
                region_id=region_id,
                polydata=pd,
                area=surface_area(pd),
                centroid=centroid(pd),
                normal=average_cell_normal(pd),
                bounds=tuple(float(x) for x in pd.GetBounds()),
            )
        )
    return regions

