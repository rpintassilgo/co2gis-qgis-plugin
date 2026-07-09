"""Unit tests for the trunk-network MILP (``src/core/networks/milp.py``).

Pure Python. The solver-backed tests are skipped when PuLP/HiGHS aren't installed (they are optional
deps); ``class_capacity`` is a plain formula and always runs.
"""

import pytest

from src.core.networks.candidate_graph import JUNCTION, CandidateArc
from src.core.networks.milp import HAS_SOLVER, class_capacity, solve_network_milp
from src.core.networks.model import SINK, SOURCE, Node

needs_solver = pytest.mark.skipif(not HAS_SOLVER, reason="PuLP/HiGHS not installed")


def _eng(**overrides):
    eng = {
        "λ": 0.015,
        "p": 827.0,
        "Δp_Ltotal": 20.0,
        "total_pressure_drop": 3.0,
        "admissible_MPa_km": 0.02,
        "Bc": 1357.0,
        "Beff": 0.75,
        "α": 0.547,
        "β": 0.42,
    }
    eng.update(overrides)
    return eng


def _nolog(*_a, **_k):
    pass


# Two sources far from the sink, sharing a junction: routing both through J and one J→K trunk is
# cheaper than two direct pipes → the MILP should form the trunk. Lengths ≪ booster spacing (150 km).
def _scenario(sink_capacity=10.0):
    nodes = [
        Node("A", 0.0, 0.0, SOURCE, flow=2.0),
        Node("B", 0.0, 10.0, SOURCE, flow=3.0),
        Node("J", 5.0, 5.0, JUNCTION),
        Node("K", 20.0, 5.0, SINK, capacity=sink_capacity),
    ]
    arcs = [
        CandidateArc("A", "J", s_cost=1.0, length=7.07),
        CandidateArc("B", "J", s_cost=1.0, length=7.07),
        CandidateArc("J", "K", s_cost=3.0, length=15.0),
        CandidateArc("A", "K", s_cost=5.0, length=20.6),
        CandidateArc("B", "K", s_cost=5.0, length=20.6),
    ]
    return nodes, arcs


def test_class_capacity_grows_with_diameter():
    eng = _eng()
    assert class_capacity(0.5, eng) > class_capacity(0.2, eng)
    assert class_capacity(0.2, eng) > 0


@needs_solver
def test_forms_a_shared_trunk_when_cheaper():
    nodes, arcs = _scenario()
    selected = solve_network_milp(nodes, arcs, target=5.0, eng=_eng(), log=_nolog)
    built = {frozenset((s.u_id, s.v_id)) for s in selected}
    assert frozenset(("J", "K")) in built  # the shared trunk is built
    assert frozenset(("A", "K")) not in built and frozenset(("B", "K")) not in built  # not the direct pipes
    trunk = next(s for s in selected if frozenset((s.u_id, s.v_id)) == frozenset(("J", "K")))
    assert trunk.flow == pytest.approx(5.0, abs=0.01)  # carries both sources' combined flow


@needs_solver
def test_capture_target_selects_a_subset():
    nodes, arcs = _scenario()
    small = solve_network_milp(nodes, arcs, target=2.0, eng=_eng(), log=_nolog)
    full = solve_network_milp(nodes, arcs, target=5.0, eng=_eng(), log=_nolog)
    assert len(small) < len(full)  # a smaller target → a smaller network (only the cheapest source)


@needs_solver
def test_infeasible_target_over_total_flow_raises():
    nodes, arcs = _scenario()
    with pytest.raises(RuntimeError):
        solve_network_milp(nodes, arcs, target=100.0, eng=_eng(), log=_nolog)  # > 2+3 available


@needs_solver
def test_infeasible_when_target_exceeds_sink_injection_rate():
    nodes, arcs = _scenario(sink_capacity=4.0)  # can't inject 5 Mt/yr into a 4 Mt/yr sink
    with pytest.raises(RuntimeError):
        solve_network_milp(nodes, arcs, target=5.0, eng=_eng(), log=_nolog)
