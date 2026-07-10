"""Pure graph construction for the pipeline-network trunks.

Turns the per-source cell chains (each source's ordered r.drain path, source→sink)
into network **segments** (edges): overlaying the chains accumulates flow where they
share the exact same cell, and the network is split into segments at the real nodes
(sources, sinks, junctions). Pure Python — no Qt / PyQGIS / GRASS — so it is unit-tested.

A cell is an ``(row, col)`` grid index. Because all of a sink's source paths drain on
the same r.cost surface, once two paths reach a common cell they follow the same
downstream cell — so the paths form a tree (merges, no crossings), and every cell has
at most one successor.
"""

from __future__ import annotations

from collections import defaultdict, namedtuple
from typing import Iterable

# One network segment: an ordered run of grid cells between two nodes, the flow it carries, and
# whether it *starts* at a junction (≥2 upstream paths merge there) — where CAPEX adds a booster.
Segment = namedtuple("Segment", ["cells", "flow", "junction"])


def build_edges(chains: Iterable) -> list:
    """Build network segments from per-source cell chains.

    :param chains: iterable of ``(flow, cells)`` — ``flow`` the source's flow and
        ``cells`` its ordered path ``[(row, col), ...]`` from source to sink.
    :returns: list of :class:`Segment`; a cell used by several chains carries the sum
        of their flows (the trunk), and each segment's ``flow`` is the flow it carries
        (``min`` of its cells' flows — the terminal junction cell holds the higher sum).
        ``junction`` is True when the segment starts where ≥2 paths merge (a trunk).
    """
    flow = defaultdict(float)
    succ = {}  # cell -> its single downstream cell
    preds = defaultdict(set)  # cell -> set of upstream cells

    for src_flow, cells in chains:
        cells = list(cells)
        if not cells:
            continue
        for cell in cells:
            flow[cell] += float(src_flow)
        for a, b in zip(cells, cells[1:]):
            succ[a] = b
            preds[b].add(a)

    def is_node(cell):
        # Source (nothing flows in), sink (nothing flows out), or junction (≥2 flow in).
        return cell not in preds or cell not in succ or len(preds[cell]) >= 2

    segments = []
    for start in flow:  # dict preserves insertion order → deterministic segment order
        if not is_node(start) or start not in succ:
            continue  # only trace outgoing edges of nodes (a sink has no successor)
        run = [start]
        cur = succ[start]
        while True:
            run.append(cur)
            if is_node(cur) or cur not in succ:
                break
            cur = succ[cur]
        is_junction = start in preds and len(preds[start]) >= 2
        segments.append(Segment(run, min(flow[c] for c in run), is_junction))
    return segments


def greedy_tree_chains(steps: Iterable, seed_cells: Iterable) -> list:
    """Assemble full source→sink chains from greedy least-cost tree growth (issue #71).

    The greedy router grows the network one source at a time: each step ties a source into the network
    as it stood then. ``cells`` is that source's r.drain path with ``cells[0]`` the source and later
    cells leading to the **nearest already-present network cell** (a seed sink, or a cell added by an
    earlier step). This accumulates parent pointers (cell → next cell toward a seed) and then rebuilds
    each source's **full** path down to a seed, so :func:`build_edges` sees the shared trunk (the
    overlapping cells) and sums flow correctly — the tie-in path alone stops at the junction.

    :param steps: ordered iterable of ``(flow, cells)`` — the tie-in paths, in build order.
    :param seed_cells: the initial network cells (the sinks) — roots of the tree.
    :returns: list of ``(flow, full_cells)`` with ``full_cells`` from the source down to a seed.
    """
    network = set(seed_cells)
    parent = dict.fromkeys(seed_cells)  # seed cells are roots (parent None)
    sources = []
    for src_flow, cells in steps:
        cells = list(cells)
        if not cells:
            continue
        join = next((i for i, c in enumerate(cells) if c in network), None)
        if join is None:
            # The tie-in cell didn't land exactly on a network cell (raster rounding) — reconnect the
            # path's end to the nearest existing network cell so the source still reaches a seed.
            nearest = min(network, key=lambda nc: (nc[0] - cells[-1][0]) ** 2 + (nc[1] - cells[-1][1]) ** 2)
            for a, b in zip(cells, cells[1:]):
                parent.setdefault(a, b)
                network.add(a)
            parent.setdefault(cells[-1], nearest)
            network.add(cells[-1])
        else:
            for a, b in zip(cells[:join], cells[1 : join + 1]):
                parent.setdefault(a, b)  # keep a cell's first (earlier) route toward the seed
                network.add(a)
        sources.append((src_flow, cells[0]))

    chains = []
    for src_flow, cell in sources:
        full, seen = [], set()
        while cell is not None and cell not in seen:
            seen.add(cell)
            full.append(cell)
            cell = parent.get(cell)
        chains.append((src_flow, full))
    return chains


def cluster_edges(edges):
    """Group network edges into clusters and identify each cluster's junctions — for a clear log.

    A **cluster** is a connected component (edges that share an endpoint); it is one source→sink tree.
    A **junction** is a trunk edge (``junction`` True) with the feeder edges whose downstream end meets
    the trunk's upstream start.

    :param edges: dicts with at least ``fid``, ``flow``, ``junction`` and — for grouping — ``start`` /
        ``end`` endpoint tuples (geometry ordered upstream→downstream). Edges without endpoints each
        form their own singleton cluster (no grouping), so the function is safe for endpoint-less input.
    :returns: list of clusters ``{"edges": [...sorted by flow...], "junctions": [{"trunk", "feeders"}]}``,
        ordered by the cluster's smallest ``fid``.
    """
    n = len(edges)
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    # Union edges that share an endpoint (skip missing endpoints → those stay singletons).
    point_edges = defaultdict(list)
    for i, e in enumerate(edges):
        for key in ("start", "end"):
            if e.get(key) is not None:
                point_edges[e[key]].append(i)
    for members in point_edges.values():
        for j in members[1:]:
            parent[find(j)] = find(members[0])

    groups = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(edges[i])

    clusters = []
    for members in groups.values():
        cl_edges = sorted(members, key=lambda e: e["flow"])
        junctions = [
            {"trunk": e, "feeders": [f for f in cl_edges if f is not e and f.get("end") == e.get("start")]}
            for e in cl_edges
            if e.get("junction")
        ]
        clusters.append({"edges": cl_edges, "junctions": junctions})

    clusters.sort(key=lambda c: min(e.get("fid", 0) for e in c["edges"]))
    return clusters
