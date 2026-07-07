"""Data model and Level-1 assignment for the pipeline-network feature.

Pure Python — no Qt, no PyQGIS — so it is unit-testable and safe off the UI
thread. A network is a set of :class:`Node` objects (sources carry an emission
``flow``, sinks carry an injection ``capacity``) joined by :class:`Edge` links.

Level 1 links each source to its nearest sink (Euclidean) as an independent
"star"; ``length``/``cost`` on each edge are filled later by the GRASS routing
stage. Later levels add shared trunks (Level 2) and MILP selection (Level 3).
"""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Iterable

SOURCE = "source"
SINK = "sink"


@dataclass(frozen=True)
class Node:
    """A network node.

    ``flow`` is set on sources (emission rate); ``capacity`` on sinks (injection
    limit). The unused one stays at 0.0. ``kind`` is :data:`SOURCE` or :data:`SINK`.
    Coordinates are in the project CRS (assumed projected, in metres).
    """

    id: str
    x: float
    y: float
    kind: str
    flow: float = 0.0
    capacity: float = 0.0


@dataclass
class Edge:
    """A directed source→sink link.

    ``length`` (m) and ``cost`` (COMET-weighted corridor cost) are filled by the
    routing stage; ``flow`` is the CO2 throughput — for the Level-1 star it equals
    the source's ``flow``.
    """

    source_id: str
    sink_id: str
    length: float = 0.0
    cost: float = 0.0
    flow: float = 0.0


def distance(a: Node, b: Node) -> float:
    """Planar Euclidean distance between two nodes (assumes a projected CRS)."""
    return hypot(a.x - b.x, a.y - b.y)


def nearest_sink(source: Node, sinks: Iterable[Node]) -> Node:
    """Return the sink closest to ``source`` by Euclidean distance.

    :raises ValueError: if ``sinks`` is empty.
    """
    sinks = list(sinks)
    if not sinks:
        raise ValueError("No sinks provided.")
    return min(sinks, key=lambda s: distance(source, s))


def assign_star(sources: Iterable[Node], sinks: Iterable[Node]) -> list[Edge]:
    """Level-1 assignment: link each source to its nearest sink, independently.

    Returns one :class:`Edge` per source, seeded with the source's ``flow``;
    ``length``/``cost`` are left at 0.0 for the routing stage to fill. No
    capacities, no trunk sharing — those are Levels 2/3.

    :raises ValueError: if ``sources`` or ``sinks`` is empty.
    """
    sources = list(sources)
    sinks = list(sinks)
    if not sources:
        raise ValueError("No sources provided.")
    if not sinks:
        raise ValueError("No sinks provided.")
    return [Edge(source_id=s.id, sink_id=nearest_sink(s, sinks).id, flow=s.flow) for s in sources]


def group_by_sink(edges: Iterable[Edge]) -> dict[str, list[Edge]]:
    """Group ``edges`` by their ``sink_id``, preserving first-seen order.

    Lets the routing stage run one ``r.cost`` accumulation per distinct used sink
    (then one ``r.drain`` per source), instead of routing each source from scratch.
    """
    grouped: dict[str, list[Edge]] = {}
    for edge in edges:
        grouped.setdefault(edge.sink_id, []).append(edge)
    return grouped
