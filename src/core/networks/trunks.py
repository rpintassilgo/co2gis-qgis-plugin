"""Level-2 heuristic: merge the independent source→sink routes into shared trunks.

Reuses the Level-1 GRASS routing (one ``r.cost`` per sink, one ``r.drain`` per
source) but, instead of stacking the route geometries, **accumulates flow**: each
source's path raster is weighted by the source's flow and summed, so every cell
carries the total flow crossing it. Where paths converge the flow rises → a trunk.

The aggregated-flow raster is the **source of truth** for flow — Price Estimation
samples it per cell at 2b (like the COMET cost rasters). The routes are also
vectorised into a plain geometry layer (for display and to walk); flow is
intentionally NOT attached to the vector, because GRASS ``r.to.vect`` does not
split a line where the raster value changes (it would fold a trunk's value into a
spur), so per-segment flow is read from the raster, not a vector attribute.

Qt-free / project-free like ``core/lcp.py``. The pure array step
(:func:`accumulate_flow`) is unit-tested.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from typing import Sequence

import numpy as np
from osgeo import gdal
from qgis import processing

from ...constants.lcp import DEFAULT_RCOST_MEMORY_MB
from ..lcp import grass_alg_id, run_r_cost, run_r_drain_raster
from .model import Node, assign_star, group_by_sink
from .routing import _coord, _slug


def path_mask(array, nodata) -> np.ndarray:
    """Boolean mask of the cells an ``r.drain`` output raster marks as the path.

    Path cells hold a value; off-path cells are NoData (or NaN). Robust to r.drain's
    exact on-path value — presence is what matters.
    """
    mask = ~np.isnan(array) if np.issubdtype(array.dtype, np.floating) else np.ones(array.shape, dtype=bool)
    if nodata is not None:
        mask &= array != nodata
    return mask


def accumulate_flow(shape, paths) -> np.ndarray:
    """Sum flow-weighted path masks into an aggregated-flow array.

    :param shape: ``(rows, cols)`` of the common grid.
    :param paths: iterable of ``(mask, flow)`` — each ``mask`` a boolean array, each
        ``flow`` the source's flow. A cell used by several sources gets their sum.
    :returns: float32 array; cell value = total flow crossing it (0 off any path).
    """
    acc = np.zeros(shape, dtype=np.float32)
    for mask, flow in paths:
        acc[mask] += float(flow)
    return acc


def _read_band(path):
    """Return ``(array, nodata, geotransform, projection)`` for band 1 of a raster."""
    ds = gdal.Open(path)
    if ds is None:
        raise RuntimeError(f"Could not open raster: {path}")
    band = ds.GetRasterBand(1)
    array = band.ReadAsArray()
    nodata = band.GetNoDataValue()
    geotrans = ds.GetGeoTransform()
    proj = ds.GetProjection()
    band = None
    ds = None
    return array, nodata, geotrans, proj


def _write_raster(array, geotrans, proj, path, gdal_type):
    """Write a single-band GeoTIFF (0 = off-path NoData)."""
    height, width = array.shape
    out = gdal.GetDriverByName("GTiff").Create(path, width, height, 1, gdal_type, options=["COMPRESS=LZW"])
    out.SetGeoTransform(geotrans)
    out.SetProjection(proj)
    band = out.GetRasterBand(1)
    band.WriteArray(array)
    band.SetNoDataValue(0)
    band.FlushCache()
    band = None
    out.FlushCache()
    out = None


def _vectorize_geometry(binary_raster: str, output_vector: str, tmp: str, log) -> str:
    """Vectorise the network path (binary raster) into a plain line-geometry layer.

    No flow attribute — flow is read from the aggregated-flow raster at 2b. r.thin
    reduces the paths to 1-cell lines so r.to.vect can extract clean lines.
    """
    thin_out = os.path.join(tmp, "path_thin.tif")
    processing.run(grass_alg_id("r.thin"), {"input": binary_raster, "output": thin_out, "iterations": 200})
    processing.run(grass_alg_id("r.to.vect"), {"input": thin_out, "type": 0, "output": output_vector})
    log("Vectorised the network geometry (flow stays in the raster).")
    return output_vector


def route_network_heuristic(
    combined_raster_path: str,
    sources: Sequence[Node],
    sinks: Sequence[Node],
    output_dir: str,
    memory: int = DEFAULT_RCOST_MEMORY_MB,
    log=lambda msg: None,
) -> dict:
    """Heuristic network design: nearest-sink routing + shared-trunk flow accumulation.

    Same routing as Level 1 (``assign_star`` → per-sink ``r.cost`` → per-source
    ``r.drain``), plus a per-cell flow sum across each sink's source paths.

    :returns: ``{"network_path", "flow_raster", "edges", "routes"}`` — the network
        geometry vector, the aggregated-flow raster (flow per cell; the source of
        truth 2b samples), the Edges (``flow`` seeded), and per-edge
        ``(source_id, sink_id)``. Does NOT touch the project.
    """
    os.makedirs(output_dir, exist_ok=True)
    edges = assign_star(sources, sinks)
    nodes_by_id = {n.id: n for n in list(sources) + list(sinks)}
    grouped = group_by_sink(edges)

    tmp = tempfile.mkdtemp()
    routes = []
    acc = None
    geotrans = proj = None
    try:
        for sink_id, sink_edges in grouped.items():
            sink = nodes_by_id[sink_id]
            log(f"r.cost accumulation from sink '{sink_id}' ({len(sink_edges)} source(s))...")
            cost_out = os.path.join(tmp, f"cost_{_slug(sink_id)}.tif")
            dir_out = os.path.join(tmp, f"dir_{_slug(sink_id)}.tif")
            cost_result = run_r_cost(combined_raster_path, _coord(sink), cost_out, dir_out, memory=memory)

            for edge in sink_edges:
                source = nodes_by_id[edge.source_id]
                drain_ras = os.path.join(tmp, f"drain_{_slug(edge.source_id)}.tif")
                log(f"  r.drain: {edge.source_id} → {sink_id} (flow {edge.flow})")
                run_r_drain_raster(cost_result, _coord(source), drain_ras, log=log)

                array, nodata, gt, pr = _read_band(drain_ras)
                if acc is None:
                    acc = np.zeros(array.shape, dtype=np.float32)
                    geotrans, proj = gt, pr
                acc[path_mask(array, nodata)] += float(edge.flow)
                routes.append((edge.source_id, sink_id))

        log("Writing aggregated-flow raster (the trunks — flow per cell)...")
        flow_raster = os.path.join(output_dir, "network_flow.tif")
        _write_raster(acc, geotrans, proj, flow_raster, gdal.GDT_Float32)

        # Vectorise the path (binary) into plain geometry — flow stays in the raster above.
        binary = (acc > 0).astype(np.int32)
        binary_raster = os.path.join(tmp, "network_path.tif")
        _write_raster(binary, geotrans, proj, binary_raster, gdal.GDT_Int32)

        log("Vectorising network geometry...")
        network_path = os.path.join(output_dir, "network.gpkg")
        _vectorize_geometry(binary_raster, network_path, tmp, log)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    log(f"✓ Heuristic network complete: {len(edges)} route(s) → trunks with per-segment flow in network.gpkg")
    return {"network_path": network_path, "flow_raster": flow_raster, "edges": edges, "routes": routes}
