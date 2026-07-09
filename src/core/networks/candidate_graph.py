"""Candidate graph for the Level-3 trunk-network MILP.

The MILP optimises over a **candidate graph**: nodes are the sources, the sinks, and a set of
**junction candidates** (a coarse grid over the study area) where flows may combine into trunks;
arcs are a pruned set of near-neighbour links. Each arc carries the COMET-cost of the least-cost
path between its endpoints (``s_cost``, from ``r.cost``) and a length estimate — these become the
per-arc coefficients of the MILP.

The graph-building helpers (:func:`junction_grid`, :func:`candidate_arcs`) are pure Python and
unit-tested; :func:`build_candidate_graph` adds the GRASS ``r.cost`` step (one run per node gives
that node's least-cost cost to every other node), validated in QGIS.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from typing import Sequence

from qgis.core import QgsPointXY, QgsRasterLayer

from ...constants.lcp import DEFAULT_RCOST_MEMORY_MB
from ..capex import get_raster_value_at_point
from ..lcp import run_r_cost
from .model import Node, distance
from .routing import _coord, _slug

JUNCTION = "junction"


@dataclass
class CandidateArc:
    """An undirected candidate link between two nodes.

    ``s_cost`` is the COMET-cost summation of the least-cost path between the endpoints (from
    ``r.cost``); ``length`` is a planar length estimate (refined by ``r.drain`` only for the arcs
    the MILP selects). The MILP adds directional flow on top of these symmetric coefficients.
    """

    u_id: str
    v_id: str
    s_cost: float
    length: float


def junction_grid(anchors: Sequence[Node], spacing: float, margin: float = 0.0) -> list[Node]:
    """Regular grid of junction-candidate nodes over the ``anchors``' bounding box (+ ``margin``).

    ``spacing`` (map units) is the density knob — smaller spacing = more candidates = a graph closer
    to the true optimum but a larger/slower MILP. Returns junction :class:`Node` objects (``kind`` =
    :data:`JUNCTION`, no flow/capacity).
    """
    if spacing <= 0:
        raise ValueError("spacing must be positive.")
    xs = [n.x for n in anchors]
    ys = [n.y for n in anchors]
    minx, maxx = min(xs) - margin, max(xs) + margin
    miny, maxy = min(ys) - margin, max(ys) + margin

    nodes = []
    idx = 0
    x = minx
    while x <= maxx + 1e-9:
        y = miny
        while y <= maxy + 1e-9:
            nodes.append(Node(id=f"J{idx}", x=x, y=y, kind=JUNCTION))
            idx += 1
            y += spacing
        x += spacing
    return nodes


def candidate_arcs(nodes: Sequence[Node], k: int = 6) -> list[tuple]:
    """Prune the O(n²) arc set to each node's ``k`` nearest neighbours (undirected, de-duplicated).

    Returns a deterministic, sorted list of ``(u_id, v_id)`` unordered pairs (``u_id < v_id``).
    """
    pairs = set()
    for a in nodes:
        nearest = sorted((b for b in nodes if b.id != a.id), key=lambda b: distance(a, b))[:k]
        for b in nearest:
            pairs.add(tuple(sorted((a.id, b.id))))
    return sorted(pairs)


def build_candidate_graph(
    combined_raster_path: str,
    sources: Sequence[Node],
    sinks: Sequence[Node],
    spacing: float,
    k: int = 6,
    memory: int = DEFAULT_RCOST_MEMORY_MB,
    log=lambda msg: None,
) -> tuple:
    """Build the candidate graph and its per-arc COMET costs for the MILP.

    Nodes = ``sources`` + ``sinks`` + a junction grid (:func:`junction_grid`); arcs = the pruned
    near-neighbour set (:func:`candidate_arcs`). One ``r.cost`` per node yields its least-cost cost
    to every other node (read at each neighbour's cell) → the per-arc ``s_cost``.

    :returns: ``(nodes, arcs)`` — ``nodes`` the full node list, ``arcs`` a list of :class:`CandidateArc`.
        Does NOT touch the project.
    """
    junctions = junction_grid(list(sources) + list(sinks), spacing)
    nodes = list(sources) + list(sinks) + junctions
    node_by_id = {n.id: n for n in nodes}
    arc_pairs = candidate_arcs(nodes, k)
    log(f"Candidate graph: {len(nodes)} nodes ({len(junctions)} junctions), {len(arc_pairs)} arcs.")

    neighbours = defaultdict(set)
    for u, v in arc_pairs:
        neighbours[u].add(v)
        neighbours[v].add(u)

    tmp = tempfile.mkdtemp()
    s_cost: dict = {}  # frozenset(u_id, v_id) -> min COMET-cost seen (symmetrise both directions)
    try:
        for i, node in enumerate(nodes, start=1):
            nbrs = neighbours[node.id]
            if not nbrs:
                continue
            log(f"  r.cost {i}/{len(nodes)} from '{node.id}'...")
            cost_out = os.path.join(tmp, f"cost_{_slug(node.id)}.tif")
            dir_out = os.path.join(tmp, f"dir_{_slug(node.id)}.tif")
            run_r_cost(combined_raster_path, _coord(node), cost_out, dir_out, memory=memory)

            layer = QgsRasterLayer(cost_out, "cost")
            if not layer.isValid():
                continue
            for vid in nbrs:
                v = node_by_id[vid]
                val = get_raster_value_at_point(layer, QgsPointXY(v.x, v.y))
                if val is None:
                    continue
                key = frozenset((node.id, vid))
                s_cost[key] = min(s_cost.get(key, val), float(val))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    arcs = []
    for u, v in arc_pairs:
        key = frozenset((u, v))
        if key not in s_cost:  # endpoint unreachable from the other on the cost surface
            continue
        arcs.append(CandidateArc(u_id=u, v_id=v, s_cost=s_cost[key], length=distance(node_by_id[u], node_by_id[v])))

    log(f"✓ Candidate graph: {len(arcs)} arcs with COMET costs.")
    return nodes, arcs
