"""Network routing → geometry: the Level-2 heuristic and the Level-3 MILP.

**Level 2** (:func:`route_network_heuristic`) routes like Level 1 (``assign_star`` → one
``r.cost`` per sink → one ``r.drain`` per source), reads each route as an ordered **chain of
grid cells**, and hands the chains to :func:`~src.core.networks.graph.build_edges`: overlapping
cells accumulate flow (the real junction) and split the network into segments.

**Level 3** (:func:`route_network_milp`) instead builds a candidate graph, solves the
fixed-charge MILP (:mod:`~src.core.networks.milp`), and ``r.drain``\\s only the **selected** links.

Both write ``network.gpkg`` with a per-segment ``flow`` + ``junction`` (priced by Price
Estimation). Qt-free / project-free like ``core/lcp.py``; the pure graph/MILP steps are unit-tested.

Heuristic limitation: paths merge only on *exact* cell overlap, so two sources whose
least-cost paths run one cell apart (parallel) stay as two segments until their cells
actually coincide — the trunk then forms late. Per-segment flow stays correct; a future
greedy corridor-discounting router (join later paths onto the built pipe) removes this.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from typing import Sequence

import numpy as np
from osgeo import gdal, ogr, osr

from ...constants.lcp import DEFAULT_RCOST_MEMORY_MB
from ..lcp import run_r_cost, run_r_drain_and_vectorize
from .candidate_graph import build_candidate_graph
from .graph import Segment, build_edges, greedy_tree_chains
from .milp import junction_flags, solve_network_milp
from .model import Node
from .routing import _coord, _slug


def _cell_of(x: float, y: float, gt) -> tuple:
    """Grid ``(row, col)`` containing map point ``(x, y)`` for geotransform ``gt``."""
    return (int((y - gt[3]) / gt[5]), int((x - gt[0]) / gt[1]))


def _cell_center(cell: tuple, gt) -> tuple:
    """Map ``(x, y)`` at the centre of grid cell ``(row, col)``."""
    row, col = cell
    return (gt[0] + (col + 0.5) * gt[1], gt[3] + (row + 0.5) * gt[5])


def _read_route_cells(vector_path: str, gt) -> list:
    """Ordered, de-duplicated grid cells of the polyline(s) in a route vector."""
    ds = ogr.Open(vector_path)
    cells = []
    if ds is not None:
        layer = ds.GetLayer()
        for feat in layer:
            geom = feat.GetGeometryRef()
            if geom is None:
                continue
            # Flatten LineString / MultiLineString to a single point sequence.
            parts = [geom.GetGeometryRef(i) for i in range(geom.GetGeometryCount())] or [geom]
            for part in parts:
                for i in range(part.GetPointCount()):
                    x, y = part.GetPoint(i)[:2]
                    cell = _cell_of(x, y, gt)
                    if not cells or cells[-1] != cell:
                        cells.append(cell)
    ds = None
    return cells


def _orient_source_to_sink(cells: list, source_xy: tuple, gt) -> list:
    """Order ``cells`` so ``cells[0]`` is the one nearest the source point."""
    if len(cells) < 2:
        return cells
    sx, sy = source_xy
    (fx, fy), (lx, ly) = _cell_center(cells[0], gt), _cell_center(cells[-1], gt)
    d_first = (fx - sx) ** 2 + (fy - sy) ** 2
    d_last = (lx - sx) ** 2 + (ly - sy) ** 2
    return cells if d_first <= d_last else list(reversed(cells))


def _write_start_raster(cells, shape, gt, proj: str, path: str) -> str:
    """Rasterize the current network cells as an r.cost start raster (1 = start, 0 = null)."""
    rows, cols = shape
    arr = np.zeros((rows, cols), dtype=np.uint8)
    for r, c in cells:
        if 0 <= r < rows and 0 <= c < cols:
            arr[r, c] = 1
    ds = gdal.GetDriverByName("GTiff").Create(path, cols, rows, 1, gdal.GDT_Byte)
    ds.SetGeoTransform(gt)
    if proj:
        ds.SetProjection(proj)
    band = ds.GetRasterBand(1)
    band.WriteArray(arr)
    band.SetNoDataValue(0)
    ds = None
    return path


def _write_network(segments, gt, proj: str, output_path: str) -> str:
    """Write the network segments to a GeoPackage (one LineString per segment).

    Each feature carries ``flow`` (Mt/yr through the segment), ``length`` (map units), and
    ``junction`` (1 if it starts at a junction — where Price Estimation adds a booster).
    """
    if os.path.exists(output_path):
        os.remove(output_path)
    driver = ogr.GetDriverByName("GPKG")
    ds = driver.CreateDataSource(output_path)
    srs = osr.SpatialReference()
    if proj:
        srs.ImportFromWkt(proj)
    layer = ds.CreateLayer("network", srs if proj else None, ogr.wkbLineString)
    layer.CreateField(ogr.FieldDefn("flow", ogr.OFTReal))
    layer.CreateField(ogr.FieldDefn("length", ogr.OFTReal))
    layer.CreateField(ogr.FieldDefn("junction", ogr.OFTInteger))
    defn = layer.GetLayerDefn()
    for seg in segments:
        line = ogr.Geometry(ogr.wkbLineString)
        for cell in seg.cells:
            x, y = _cell_center(cell, gt)
            line.AddPoint_2D(x, y)
        feat = ogr.Feature(defn)
        feat.SetGeometry(line)
        feat.SetField("flow", float(seg.flow))
        feat.SetField("length", float(line.Length()))
        feat.SetField("junction", 1 if seg.junction else 0)
        layer.CreateFeature(feat)
        feat = None
    ds = None
    return output_path


def route_network_heuristic(
    combined_raster_path: str,
    sources: Sequence[Node],
    sinks: Sequence[Node],
    output_path: str,
    memory: int = DEFAULT_RCOST_MEMORY_MB,
    log=lambda msg: None,
) -> dict:
    """Heuristic network design: a greedy least-cost tree (Prim on the cost surface, issue #71).

    Seeds the network with the sink cells, then adds sources one at a time (largest flow first): each
    ``r.cost`` accumulation starts from the **whole network built so far** (multi-origin), and the
    source's ``r.drain`` ties it into the **nearest existing network cell** — a built pipe (forming a
    shared trunk / a source→source gathering line) or a sink. Full source→sink chains are then rebuilt
    (:func:`~graph.greedy_tree_chains`) and handed to :func:`~graph.build_edges` for per-segment flow.
    The network is written to ``output_path`` (a GeoPackage). Unlike routing each source independently,
    later paths join the corridor already built instead of running parallel and merging late.

    :returns: ``{"network_path", "segments", "routes"}`` — the network vector (per-segment ``flow`` +
        ``length``), the :class:`~graph.Segment` list, and the gathered source ids. Does NOT touch the
        project.
    """
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    ras = gdal.Open(combined_raster_path)
    if ras is None:
        raise RuntimeError(f"Could not open combined raster: {combined_raster_path}")
    gt = ras.GetGeoTransform()
    proj = ras.GetProjection()
    shape = (ras.RasterYSize, ras.RasterXSize)
    ras = None

    # Seed the network with the sink cells; grow it one source at a time (largest flow first, so the
    # trunk to a sink is laid before the small spurs that snap onto it).
    seed_cells = [_cell_of(sink.x, sink.y, gt) for sink in sinks]
    network_cells = set(seed_cells)
    ordered = sorted(sources, key=lambda s: s.flow, reverse=True)

    tmp = tempfile.mkdtemp()
    steps = []
    routes = []
    try:
        for i, source in enumerate(ordered, start=1):
            log(
                f"r.cost from the network ({len(network_cells)} cell(s)) → tie in source '{source.id}' "
                f"({i}/{len(ordered)}, flow {source.flow:g})..."
            )
            start_ras = _write_start_raster(network_cells, shape, gt, proj, os.path.join(tmp, f"net_{i}.tif"))
            cost_out = os.path.join(tmp, f"cost_{_slug(source.id)}.tif")
            dir_out = os.path.join(tmp, f"dir_{_slug(source.id)}.tif")
            cost_result = run_r_cost(
                combined_raster_path, None, cost_out, dir_out, memory=memory, start_raster=start_ras
            )

            route_vec = os.path.join(tmp, f"route_{_slug(source.id)}.gpkg")
            run_r_drain_and_vectorize(cost_result, _coord(source), route_vec, log=log)
            cells = _orient_source_to_sink(_read_route_cells(route_vec, gt), (source.x, source.y), gt)
            if len(cells) >= 2:
                steps.append((source.flow, cells))
                network_cells.update(cells)
            routes.append(source.id)

        log("Building the network graph (full chains → per-segment flow at the real junctions)...")
        chains = greedy_tree_chains(steps, seed_cells)
        segments = build_edges(chains)
        _write_network(segments, gt, proj, output_path)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    log(f"✓ Network tree: {len(segments)} segment(s) from {len(routes)} source(s) → {os.path.basename(output_path)}")
    return {"network_path": output_path, "segments": segments, "routes": routes}


def route_network_milp(
    combined_raster_path: str,
    sources: Sequence[Node],
    sinks: Sequence[Node],
    target: float,
    output_path: str,
    spacing: float,
    eng: dict,
    k: int = 6,
    memory: int = DEFAULT_RCOST_MEMORY_MB,
    log=lambda msg: None,
) -> dict:
    """MILP network design: candidate graph → fixed-charge MILP → r.drain the selected links.

    Builds the candidate graph (:func:`~candidate_graph.build_candidate_graph`), solves the
    trunk-network MILP (:func:`~milp.solve_network_milp` — which links to build, at which pipe size,
    to meet the ``target`` (Mt/yr) within the sinks' injection rates), then ``r.drain``\\s only the
    selected links and writes them to ``output_path`` with per-segment ``flow`` + ``junction`` — the
    same format the Level-2 heuristic produces, so Price Estimation prices it the same way.

    :returns: ``{"network_path", "segments", "selected"}``. Does NOT touch the project.
    """
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    ras = gdal.Open(combined_raster_path)
    if ras is None:
        raise RuntimeError(f"Could not open combined raster: {combined_raster_path}")
    gt, proj = ras.GetGeoTransform(), ras.GetProjection()
    ras = None

    nodes, arcs = build_candidate_graph(combined_raster_path, sources, sinks, spacing, k, memory=memory, log=log)
    selected = solve_network_milp(nodes, arcs, target, eng, log=log)
    flags = junction_flags(selected, [s.id for s in sources], [s.id for s in sinks])
    node_by_id = {n.id: n for n in nodes}

    tmp = tempfile.mkdtemp()
    segments = []
    try:
        for arc in selected:
            up, down = node_by_id[arc.u_id], node_by_id[arc.v_id]
            log(f"  r.drain: {arc.u_id} → {arc.v_id} (flow {arc.flow:g} Mt/yr, D {arc.diameter * 1000:.0f} mm)")
            cost_out = os.path.join(tmp, f"cost_{_slug(arc.u_id)}.tif")
            dir_out = os.path.join(tmp, f"dir_{_slug(arc.u_id)}.tif")
            cost_result = run_r_cost(combined_raster_path, _coord(up), cost_out, dir_out, memory=memory)
            route_vec = os.path.join(tmp, f"arc_{_slug(arc.u_id)}_{_slug(arc.v_id)}.gpkg")
            run_r_drain_and_vectorize(cost_result, _coord(down), route_vec, log=log)

            cells = _orient_source_to_sink(_read_route_cells(route_vec, gt), (up.x, up.y), gt)
            if len(cells) >= 2:
                segments.append(Segment(cells, arc.flow, flags[(arc.u_id, arc.v_id)]))
        _write_network(segments, gt, proj, output_path)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    log(f"✓ MILP network: {len(segments)} link(s) → {os.path.basename(output_path)}")
    return {"network_path": output_path, "segments": segments, "selected": selected}
