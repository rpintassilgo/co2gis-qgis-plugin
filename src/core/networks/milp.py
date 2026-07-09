"""Level-3 trunk-network MILP — pick the provably minimum-cost network.

A **fixed-charge network-design MILP** over the candidate graph (:mod:`candidate_graph`): choose which
links to build and at which **standard pipe size**, and how CO2 routes from sources through junction
nodes to sinks, so a **capture target** (Mt/yr) is met within each sink's **injection rate**, at minimum
cost. Trunks emerge because a link carrying several sources' combined flow (via conservation at
junctions) picks a larger, cheaper-per-unit size — the economy of scale, exact under discrete sizing.

Modelled in **PuLP**, solved with **HiGHS** — both optional MIT deps. The MILP is available only when
both import (:data:`HAS_SOLVER`); everything here is pure Python (no Qt/GRASS) and unit-tested on
synthetic graphs. Per-arc *flow*, *diameter* and *selection* are MILP **outputs**.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict, namedtuple
from typing import Sequence

from ..capex import SECONDS_PER_YEAR, _booster_cost, mt_yr_to_kg_s
from .model import SINK, SOURCE

try:
    import highspy  # noqa: F401  (HiGHS backend for PuLP)
    import pulp

    HAS_SOLVER = True
except ImportError:  # pragma: no cover - depends on the environment
    HAS_SOLVER = False

# Standard inner pipe diameters (m). Domain input — confirm against the case study.
DIAMETER_CLASSES = (0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0)

# One selected pipe: the undirected link, its chosen diameter (m), and the flow it carries (Mt/yr).
SelectedArc = namedtuple("SelectedArc", ["u_id", "v_id", "diameter", "flow"])


def class_capacity(diameter: float, eng: dict) -> float:
    """Max flow (Mt/yr) a pipe of inner ``diameter`` (m) carries at the admissible pressure gradient.

    Darcy-Weisbach inverted: ``D = (8λM²/(π²ρ·Δp_L))^(1/5)`` → ``M = √(π²ρ·Δp_L·D⁵/(8λ))`` (kg/s), then
    kg/s → Mt/yr. This is the diameter class's flow capacity used in the MILP.
    """
    m_kg_s = math.sqrt((math.pi**2) * eng["p"] * eng["Δp_Ltotal"] * diameter**5 / (8 * eng["λ"]))
    return m_kg_s * SECONDS_PER_YEAR / 1e9


def _arc_cost(s_cost: float, length: float, diameter: float, capacity: float, max_seg: float, eng: dict) -> float:
    """Fixed (build) cost of one link at a given diameter: COMET pipe cost + a spacing-booster estimate.

    Pipe ``Bc·D·S`` (``S`` = COMET summation along the arc, from r.cost) plus one booster per full
    ``max_seg`` of length, sized at the class's design flow. Constant per (arc, class) → keeps the MILP
    linear; the *exact* CAPEX (with real flows + junction boosters) is recomputed after solving.
    """
    pipe = eng["Bc"] * diameter * s_cost
    n_boosters = int(length // max_seg)
    boosters = n_boosters * _booster_cost(mt_yr_to_kg_s(capacity), eng) if n_boosters else 0.0
    return pipe + boosters


def solve_network_milp(nodes: Sequence, arcs: Sequence, target: float, eng: dict, log=lambda msg: None) -> list:
    """Solve the trunk-network MILP and return the links to build.

    :param nodes: candidate nodes — sources (``flow``), sinks (``capacity``), junctions (:mod:`model`).
    :param arcs: :class:`~candidate_graph.CandidateArc` list (``u_id, v_id, s_cost, length``).
    :param target: capture target (Mt/yr) — the network must move at least this much.
    :param eng: physics dict (``λ, p, Δp_Ltotal, total_pressure_drop, admissible_MPa_km, Bc, Beff, α, β``).
    :returns: list of :class:`SelectedArc` (built link, chosen diameter, carried flow).
    :raises RuntimeError: if the solver isn't installed, or the problem is infeasible / not optimal.
    """
    if not HAS_SOLVER:
        raise RuntimeError("MILP solver not available — install it with: pip install highspy pulp")

    sources = [n for n in nodes if n.kind == SOURCE]
    sinks = [n for n in nodes if n.kind == SINK]
    classes = [(d, class_capacity(d, eng)) for d in DIAMETER_CLASSES]
    max_seg = (eng["total_pressure_drop"] / eng["admissible_MPa_km"]) * 1000  # km → m

    prob = pulp.LpProblem("trunk_network", pulp.LpMinimize)

    # Directed flow vars (a physical pipe is undirected; flow picks a direction).
    directed = [p for a in arcs for p in ((a.u_id, a.v_id), (a.v_id, a.u_id))]
    flow = {p: pulp.LpVariable(f"flow_{p[0]}_{p[1]}", lowBound=0) for p in directed}
    # Build vars: undirected link a at diameter class di.
    build = {
        (a.u_id, a.v_id, di): pulp.LpVariable(f"build_{a.u_id}_{a.v_id}_{di}", cat="Binary")
        for a in arcs
        for di in range(len(classes))
    }
    x = {s.id: pulp.LpVariable(f"x_{s.id}", cat="Binary") for s in sources}  # source captured?
    sink_in = {s.id: pulp.LpVariable(f"sink_{s.id}", lowBound=0, upBound=s.capacity) for s in sinks}

    # Objective: minimise total build cost.
    prob += pulp.lpSum(
        _arc_cost(a.s_cost, a.length, classes[di][0], classes[di][1], max_seg, eng) * build[(a.u_id, a.v_id, di)]
        for a in arcs
        for di in range(len(classes))
    )

    for a in arcs:
        # one diameter per built link; flow (either direction) capped by the chosen class capacity.
        prob += pulp.lpSum(build[(a.u_id, a.v_id, di)] for di in range(len(classes))) <= 1
        prob += flow[(a.u_id, a.v_id)] + flow[(a.v_id, a.u_id)] <= pulp.lpSum(
            classes[di][1] * build[(a.u_id, a.v_id, di)] for di in range(len(classes))
        )

    # Flow conservation at every node.
    out_arcs, in_arcs = defaultdict(list), defaultdict(list)
    for u, v in directed:
        out_arcs[u].append((u, v))
        in_arcs[v].append((u, v))
    for n in nodes:
        outflow = pulp.lpSum(flow[e] for e in out_arcs[n.id])
        inflow = pulp.lpSum(flow[e] for e in in_arcs[n.id])
        if n.kind == SOURCE:
            prob += outflow - inflow == n.flow * x[n.id]
        elif n.kind == SINK:
            prob += inflow - outflow == sink_in[n.id]  # ≤ capacity via the var's upBound
        else:  # junction — pass-through (trunks form here)
            prob += inflow - outflow == 0

    prob += pulp.lpSum(s.flow * x[s.id] for s in sources) >= target  # capture target

    status = prob.solve(_pulp_highs_solver())
    if pulp.LpStatus[status] != "Optimal":
        raise RuntimeError(
            f"MILP not solved to optimality ({pulp.LpStatus[status]}). "
            "The capture target may exceed the reachable sources or the sinks' injection rates."
        )

    selected = []
    for a in arcs:
        for di, (diameter, _cap) in enumerate(classes):
            if (build[(a.u_id, a.v_id, di)].value() or 0) > 0.5:
                f_uv = flow[(a.u_id, a.v_id)].value() or 0
                f_vu = flow[(a.v_id, a.u_id)].value() or 0
                # Orient the arc along the flow (upstream → downstream) so junctions can be read.
                up, down = (a.u_id, a.v_id) if f_uv >= f_vu else (a.v_id, a.u_id)
                selected.append(SelectedArc(up, down, diameter, f_uv + f_vu))
    log(f"✓ MILP: {len(selected)} link(s) built, total cost {pulp.value(prob.objective):,.0f} €.")
    return selected


def junction_flags(selected: Sequence) -> dict:
    """Which oriented arcs start at a **junction** (≥2 arcs feed their upstream node → a trunk).

    :param selected: :class:`SelectedArc` list oriented upstream→downstream (from
        :func:`solve_network_milp`).
    :returns: ``{(u_id, v_id): bool}`` — True where the arc's upstream node is a merge point.
    """
    in_degree = Counter(arc.v_id for arc in selected)  # nodes that are a downstream endpoint
    return {(arc.u_id, arc.v_id): in_degree[arc.u_id] >= 2 for arc in selected}


def _pulp_highs_solver():
    """PuLP HiGHS solver (via highspy), silent. Falls back to the HiGHS CLI if the class is absent."""
    if hasattr(pulp, "HiGHS"):
        return pulp.HiGHS(msg=False)
    return pulp.HiGHS_CMD(msg=False)
