"""Unit tests for the pipeline-network data model + Level-1 assignment
(``src/core/networks/model.py``). Pure Python — no QGIS required.
"""

import pytest

from src.core.networks.model import SINK, SOURCE, Node, assign_star, distance, nearest_sink


def _src(node_id, x, y, flow=1.0):
    return Node(id=node_id, x=x, y=y, kind=SOURCE, flow=flow)


def _snk(node_id, x, y, capacity=10.0):
    return Node(id=node_id, x=x, y=y, kind=SINK, capacity=capacity)


def test_distance_is_euclidean():
    assert distance(_src("A", 0, 0), _snk("X", 3, 4)) == 5.0


def test_nearest_sink_picks_closest():
    source = _src("A", 0, 0)
    near = _snk("near", 1, 0)
    far = _snk("far", 10, 0)
    assert nearest_sink(source, [far, near]) is near


def test_nearest_sink_requires_sinks():
    with pytest.raises(ValueError):
        nearest_sink(_src("A", 0, 0), [])


def test_assign_star_links_each_source_to_nearest_sink():
    sources = [_src("A", 0, 0), _src("B", 10, 0)]
    sinks = [_snk("X", 1, 0), _snk("Y", 9, 0)]
    edges = assign_star(sources, sinks)
    assert {(e.source_id, e.sink_id) for e in edges} == {("A", "X"), ("B", "Y")}


def test_assign_star_seeds_edge_flow_from_source():
    edges = assign_star([_src("A", 0, 0, flow=2.5)], [_snk("X", 1, 1)])
    assert edges[0].flow == 2.5


def test_assign_star_leaves_length_and_cost_for_routing():
    edge = assign_star([_src("A", 0, 0)], [_snk("X", 1, 1)])[0]
    assert edge.length == 0.0
    assert edge.cost == 0.0


def test_assign_star_one_edge_per_source():
    sources = [_src("A", 0, 0), _src("B", 5, 5), _src("C", -3, 2)]
    edges = assign_star(sources, [_snk("X", 0, 0)])
    assert len(edges) == len(sources)


def test_assign_star_requires_sources_and_sinks():
    with pytest.raises(ValueError):
        assign_star([], [_snk("X", 0, 0)])
    with pytest.raises(ValueError):
        assign_star([_src("A", 0, 0)], [])
