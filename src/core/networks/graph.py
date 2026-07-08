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
