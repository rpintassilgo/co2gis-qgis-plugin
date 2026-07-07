"""GRASS-backed star routing for the pipeline-network feature (dormant).

Turns a Level-1 assignment (each source → its nearest sink) into real pipeline
geometries by reusing the single-LCP GRASS chain in ``src/core/lcp.py``: one
``r.cost`` accumulation per distinct used sink, then one ``r.drain`` per source on
that surface. Qt-free and project-free (like ``core/lcp.py``), so it is safe to
call off the UI thread; the caller loads the result from the main thread.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from typing import Sequence

from qgis.core import QgsPointXY, QgsRasterLayer, QgsVectorLayer

from ...constants.lcp import DEFAULT_RCOST_MEMORY_MB
from ..aux import combine_vectors
from ..capex import get_raster_value_at_point
from ..lcp import run_r_cost, run_r_drain_and_vectorize
from .model import Node, assign_star, group_by_sink


def _coord(node: Node) -> str:
    """GRASS ``"x,y"`` start-coordinate string (6 dp, mirrors the LCP tab)."""
    return f"{node.x:.6f},{node.y:.6f}"


def _slug(node_id: str) -> str:
    """Make a node id safe to embed in an output filename."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in str(node_id))


def route_star(
    combined_raster_path: str,
    sources: Sequence[Node],
    sinks: Sequence[Node],
    output_dir: str,
    memory: int = DEFAULT_RCOST_MEMORY_MB,
    log=lambda msg: None,
) -> dict:
    """Route each source to its nearest sink as an independent least-cost path.

    Runs one ``r.cost`` accumulation per distinct used sink, then one ``r.drain``
    per source on that surface. Fills each :class:`~src.core.networks.model.Edge`
    with its route ``length`` and (best-effort) ``cost``, and merges the per-edge
    vectors into a single network layer.

    :param combined_raster_path: the COMET combined cost raster (an LCP-tab output).
    :param sources: source nodes (each with a ``flow``).
    :param sinks: sink nodes (each with a ``capacity``).
    :param output_dir: directory for the per-edge vectors and the merged network.
    :param memory: r.cost RAM budget (MB).
    :returns: ``{"network_path", "edges", "routes"}`` — the merged network vector
        path, the Edges with ``length``/``cost`` filled, and per-edge
        ``(source_id, sink_id, path)`` tuples. Does NOT touch the project.
    """
    os.makedirs(output_dir, exist_ok=True)
    edges = assign_star(sources, sinks)
    nodes_by_id = {n.id: n for n in list(sources) + list(sinks)}
    grouped = group_by_sink(edges)

    tmp = tempfile.mkdtemp()
    routes = []
    try:
        for sink_id, sink_edges in grouped.items():
            sink = nodes_by_id[sink_id]
            log(f"r.cost accumulation from sink '{sink_id}' ({len(sink_edges)} source(s))...")
            cost_out = os.path.join(tmp, f"cost_{_slug(sink_id)}.tif")
            dir_out = os.path.join(tmp, f"dir_{_slug(sink_id)}.tif")
            cost_result = run_r_cost(combined_raster_path, _coord(sink), cost_out, dir_out, memory=memory)

            accum_layer = QgsRasterLayer(cost_result["output"], "accum")
            for edge in sink_edges:
                source = nodes_by_id[edge.source_id]
                route_path = os.path.join(output_dir, f"route_{_slug(edge.source_id)}_to_{_slug(sink_id)}.gpkg")
                log(f"  r.drain: {edge.source_id} → {sink_id}")
                run_r_drain_and_vectorize(cost_result, _coord(source), route_path, log=log)

                layer = QgsVectorLayer(route_path, "route", "ogr")
                if layer.isValid():
                    edge.length = sum(f.geometry().length() for f in layer.getFeatures())
                if accum_layer.isValid():
                    value = get_raster_value_at_point(accum_layer, QgsPointXY(source.x, source.y))
                    if value is not None:
                        edge.cost = float(value)

                routes.append((edge.source_id, sink_id, route_path))

        log("Merging routes into one network layer...")
        network_path = os.path.join(output_dir, "network.gpkg")
        combine_vectors([path for _, _, path in routes], network_path, log=log)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    log(f"✓ Star routing complete: {len(edges)} pipeline(s) → {network_path}")
    return {"network_path": network_path, "edges": edges, "routes": routes}
