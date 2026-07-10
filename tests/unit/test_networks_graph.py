"""Unit tests for the pure network-graph builder (``src/core/networks/graph.py``).

Pure Python — no QGIS/GRASS. Covers overlaying source cell-chains into segments:
flow accumulates where chains share a cell (the trunk), and the network splits into
segments at the real junctions.
"""

from src.core.networks.graph import build_edges, cluster_edges, greedy_tree_chains


def _flows(segments):
    return sorted(round(seg.flow, 3) for seg in segments)


def test_two_chains_merge_into_a_trunk():
    # A (2.0) and B (3.0) meet at (1,2) then run together to the sink (2,2).
    a = (2.0, [(0, 0), (0, 1), (1, 2), (2, 2)])
    b = (3.0, [(0, 4), (0, 3), (1, 2), (2, 2)])
    segments = build_edges([a, b])
    # 3 segments: spur A (2), spur B (3), trunk (2+3=5).
    assert len(segments) == 3
    assert _flows(segments) == [2.0, 3.0, 5.0]


def test_trunk_segment_spans_junction_to_sink():
    a = (2.0, [(0, 0), (0, 1), (1, 2), (2, 2)])
    b = (3.0, [(0, 4), (0, 3), (1, 2), (2, 2)])
    trunk = next(s for s in build_edges([a, b]) if round(s.flow, 3) == 5.0)
    # The trunk runs from the junction (1,2) to the sink (2,2) — the shared cells only.
    assert trunk.cells == [(1, 2), (2, 2)]


def test_spur_ends_at_the_junction():
    a = (2.0, [(0, 0), (0, 1), (1, 2), (2, 2)])
    b = (3.0, [(0, 4), (0, 3), (1, 2), (2, 2)])
    spur_a = next(s for s in build_edges([a, b]) if round(s.flow, 3) == 2.0)
    assert spur_a.cells[0] == (0, 0)  # source
    assert spur_a.cells[-1] == (1, 2)  # junction


def test_trunk_is_flagged_as_junction_spurs_are_not():
    a = (2.0, [(0, 0), (0, 1), (1, 2), (2, 2)])
    b = (3.0, [(0, 4), (0, 3), (1, 2), (2, 2)])
    segments = build_edges([a, b])
    trunk = next(s for s in segments if round(s.flow, 3) == 5.0)
    spurs = [s for s in segments if round(s.flow, 3) != 5.0]
    assert trunk.junction is True  # starts where the two spurs merge
    assert all(s.junction is False for s in spurs)


def test_single_chain_is_one_segment():
    segments = build_edges([(4.0, [(0, 0), (0, 1), (0, 2)])])
    assert len(segments) == 1
    assert segments[0].flow == 4.0
    assert segments[0].cells == [(0, 0), (0, 1), (0, 2)]


def test_three_chains_stack_their_flows():
    # Three spurs converging on the same junction (5,5) → sink (6,5).
    chains = [
        (1.0, [(0, 5), (5, 5), (6, 5)]),
        (2.0, [(5, 0), (5, 5), (6, 5)]),
        (4.0, [(5, 9), (5, 5), (6, 5)]),
    ]
    segments = build_edges(chains)
    assert _flows(segments) == [1.0, 2.0, 4.0, 7.0]  # three spurs + trunk (1+2+4)


def test_empty_chains_give_no_segments():
    assert build_edges([]) == []
    assert build_edges([(2.0, [])]) == []


def test_greedy_tree_chains_rebuilds_full_paths_and_forms_a_trunk():
    # Sink at (0,0). A ties straight in; B is routed later and ties into A's trunk mid-way at (0,2),
    # so B's tie-in path stops there — greedy_tree_chains must extend it down to the sink.
    seed = [(0, 0)]
    steps = [
        (2.0, [(0, 3), (0, 2), (0, 1), (0, 0)]),  # A → sink
        (3.0, [(0, 5), (0, 4), (1, 3), (0, 2)]),  # B → ties into A's trunk at (0,2)
    ]
    chains = greedy_tree_chains(steps, seed)
    lengths = sorted(len(cells) for _flow, cells in chains)
    assert lengths == [4, 6]  # A: 4 cells; B extended (0,5)(0,4)(1,3)(0,2)(0,1)(0,0) = 6
    segments = build_edges(chains)
    assert max(s.flow for s in segments) == 5.0  # the shared trunk carries 2+3
    assert any(s.junction for s in segments)  # a junction forms where B meets A


def test_greedy_tree_chains_reconnects_a_tie_in_that_misses_by_a_cell():
    # B's path ends at (0,3), one cell short of A's trunk (which occupies (0,2)…). It must reconnect
    # to the nearest network cell instead of becoming a second, sink-less root.
    seed = [(0, 0)]
    steps = [
        (2.0, [(0, 2), (0, 1), (0, 0)]),  # A → sink, occupies (0,2),(0,1),(0,0)
        (3.0, [(0, 5), (0, 4), (0, 3)]),  # B ends at (0,3) — not on the network
    ]
    chains = greedy_tree_chains(steps, seed)
    b = next(cells for _flow, cells in chains if cells[0] == (0, 5))
    assert b[-1] == (0, 0)  # B still reaches the sink after reconnecting to the nearest cell


def test_cluster_edges_groups_and_finds_junction_feeders():
    # Two independent clusters, each: two spurs ending at a junction where the trunk starts.
    edges = [
        {"fid": 1, "flow": 2.5, "junction": False, "start": (0, 0), "end": (5, 5)},
        {"fid": 3, "flow": 1.8, "junction": False, "start": (0, 10), "end": (5, 5)},
        {"fid": 2, "flow": 4.3, "junction": True, "start": (5, 5), "end": (10, 10)},
        {"fid": 4, "flow": 1.2, "junction": False, "start": (20, 0), "end": (25, 5)},
        {"fid": 6, "flow": 0.9, "junction": False, "start": (20, 10), "end": (25, 5)},
        {"fid": 5, "flow": 2.1, "junction": True, "start": (25, 5), "end": (30, 10)},
    ]
    clusters = cluster_edges(edges)
    assert len(clusters) == 2

    first = clusters[0]  # ordered by smallest fid → the cluster containing fid 1
    assert [e["fid"] for e in first["edges"]] == [3, 1, 2]  # sorted by flow: 1.8, 2.5, 4.3
    assert len(first["junctions"]) == 1
    junction = first["junctions"][0]
    assert junction["trunk"]["fid"] == 2
    assert sorted(f["fid"] for f in junction["feeders"]) == [1, 3]


def test_cluster_edges_without_endpoints_are_singletons():
    # Endpoint-less edges (e.g. unit tests / non-2a input) must not be grouped together.
    edges = [{"fid": 1, "flow": 2.0, "junction": False}, {"fid": 2, "flow": 3.0, "junction": True}]
    assert len(cluster_edges(edges)) == 2
