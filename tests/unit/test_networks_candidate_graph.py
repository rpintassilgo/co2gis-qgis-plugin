"""Unit tests for the pure candidate-graph helpers (``src/core/networks/candidate_graph.py``).

The junction grid and the k-nearest arc pruning are pure Python (no GRASS); the r.cost step in
``build_candidate_graph`` is validated in QGIS, not here.
"""

import pytest

from src.core.networks.candidate_graph import JUNCTION, candidate_arcs, junction_grid
from src.core.networks.model import SINK, SOURCE, Node


def test_junction_grid_covers_the_bounding_box():
    anchors = [Node("S1", 0.0, 0.0, SOURCE), Node("K1", 10.0, 10.0, SINK)]
    grid = junction_grid(anchors, spacing=5.0)
    # x, y each ∈ {0, 5, 10} → 3×3 nodes, all junctions.
    assert len(grid) == 9
    assert all(n.kind == JUNCTION for n in grid)
    coords = {(n.x, n.y) for n in grid}
    assert {(0.0, 0.0), (5.0, 5.0), (10.0, 10.0)} <= coords


def test_junction_grid_applies_the_margin():
    grid = junction_grid([Node("S1", 0.0, 0.0, SOURCE)], spacing=5.0, margin=5.0)
    # single anchor, ±5 margin → x, y ∈ {-5, 0, 5} → 9 nodes.
    assert len(grid) == 9


def test_junction_grid_rejects_non_positive_spacing():
    with pytest.raises(ValueError):
        junction_grid([Node("S1", 0.0, 0.0, SOURCE)], spacing=0.0)


def test_candidate_arcs_are_knn_undirected_deduped_sorted():
    nodes = [Node("A", 0.0, 0.0, JUNCTION), Node("B", 1.0, 0.0, JUNCTION), Node("C", 5.0, 0.0, JUNCTION)]
    # nearest: A↔B, B↔A, C→B → the undirected set {A-B, B-C}, sorted with u_id < v_id.
    assert candidate_arcs(nodes, k=1) == [("A", "B"), ("B", "C")]


def test_candidate_arcs_more_neighbours_include_all_close_pairs():
    nodes = [Node("A", 0.0, 0.0, JUNCTION), Node("B", 1.0, 0.0, JUNCTION), Node("C", 2.0, 0.0, JUNCTION)]
    arcs = candidate_arcs(nodes, k=2)
    # every pair is within the 2 nearest → the full undirected set.
    assert arcs == [("A", "B"), ("A", "C"), ("B", "C")]
    assert all(u < v for u, v in arcs)  # unordered pairs, u_id < v_id
