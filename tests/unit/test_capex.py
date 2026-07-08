"""Unit tests for the CAPEX math (``src/core/capex.py``).

``compute_capex`` (diameter + segment splitting + booster placement) and
``get_intersected_cells`` (line rasterization) are pure functions. The QGIS/GDAL
imports at the top of the module are stubbed in ``conftest.py`` so this runs
without a QGIS runtime.
"""

import numpy as np
import pytest

from src.core.capex import compute_capex, get_intersected_cells


def _eng(**overrides):
    """Reference engineering defaults (mirror ``src/constants/capex.py`` + the UI)."""
    eng = {
        "λ": 0.015,
        "M": 1.0,
        "p": 827.0,
        "Δp_Ltotal": 20.0,  # 0.02 MPa/km expressed in Pa/m
        "total_pressure_drop": 3.0,  # MPa
        "admissible_MPa_km": 0.02,  # MPa/km
        "Bc": 1357.0,
        "Beff": 0.75,
        "α": 0.547,
        "β": 0.42,
    }
    eng.update(overrides)
    return eng


def _nolog(*_args, **_kwargs):
    """Swallow the progress callback ``compute_capex`` expects."""


def _diameter(eng):
    return ((8 * eng["λ"] * eng["M"] ** 2) / (np.pi**2 * eng["p"] * eng["Δp_Ltotal"])) ** (1 / 5)


def test_single_neutral_cell_matches_ip_formula():
    eng = _eng()
    values = [(1.0, 1.0, 1.0, 1.0, 0, 1000.0)]  # one 1 km neutral cell
    out = compute_capex(values, eng, _nolog)
    # summation = comet(1,1,1,1,0)·1000 = 1000; Ip = Bc·D·1000; no booster.
    assert out["I_total"] == pytest.approx(eng["Bc"] * _diameter(eng) * 1000.0)


def test_route_at_limit_has_no_booster():
    eng = _eng()
    # 150 × 1 km = 150 km. The final segment closes exactly at the limit on the
    # last cell, so no intermediate booster is inserted.
    values = [(1.0, 1.0, 1.0, 1.0, 0, 1000.0)] * 150
    out = compute_capex(values, eng, _nolog)
    assert out["I_total"] == pytest.approx(eng["Bc"] * _diameter(eng) * 150_000.0)


def test_route_over_limit_inserts_one_booster():
    eng = _eng()
    # 151 × 1 km = 151 km → first segment closes at 150 km (one booster), then a
    # 1 km final segment.
    values = [(1.0, 1.0, 1.0, 1.0, 0, 1000.0)] * 151
    out = compute_capex(values, eng, _nolog)

    pipe = eng["Bc"] * _diameter(eng) * 151_000.0
    max_seg = (eng["total_pressure_drop"] / eng["admissible_MPa_km"]) * 1000  # 150000 m
    dP = eng["Δp_Ltotal"] * max_seg  # Pa over a full segment
    Sc_MW = (eng["M"] * dP) / (eng["p"] * eng["Beff"]) / 1e6
    Ib = (eng["α"] * Sc_MW + eng["β"]) * 1e6
    assert out["I_total"] == pytest.approx(pipe + Ib)


def test_every_cell_counted_including_last():
    # Regression for #15: the final cell must always be included. The old
    # float-sum comparison could drop it and return I_total == 0.
    eng = _eng()
    values = [(1.0, 1.0, 1.0, 1.0, 0, 0.1)] * 3  # tiny fractional lengths
    out = compute_capex(values, eng, _nolog)
    assert out["I_total"] > 0
    assert out["I_total"] == pytest.approx(eng["Bc"] * _diameter(eng) * 0.3)


def test_costlier_land_use_raises_capex():
    eng = _eng()
    cheap = compute_capex([(1.0, 1.0, 1.0, 1.0, 0, 1000.0)], eng, _nolog)["I_total"]
    dear = compute_capex([(1.0, 1.0, 1.8, 1.0, 0, 1000.0)], eng, _nolog)["I_total"]
    assert dear == pytest.approx(cheap * 1.8)


def test_get_intersected_cells_horizontal_line():
    # A horizontal segment crossing three cells in row 0 of a 1×1 grid whose
    # top-left origin is (0, 10).
    cells = get_intersected_cells(
        x1=0.5,
        y1=9.5,
        x2=2.5,
        y2=9.5,
        origin_x=0.0,
        origin_y=10.0,
        cell_width=1.0,
        cell_height=1.0,
        grid_width=5,
        grid_height=5,
    )
    assert set(cells) == {(0, 0), (1, 0), (2, 0)}


def test_get_intersected_cells_clips_to_grid():
    # Endpoints outside the grid must not produce out-of-bounds cells.
    cells = get_intersected_cells(
        x1=-5.0,
        y1=9.5,
        x2=1.5,
        y2=9.5,
        origin_x=0.0,
        origin_y=10.0,
        cell_width=1.0,
        cell_height=1.0,
        grid_width=3,
        grid_height=3,
    )
    assert all(0 <= c < 3 and 0 <= r < 3 for c, r in cells)


# ── Network CAPEX (Level 2b): per-segment diameter + junction boosters ──────────────

from src.core.capex import (  # noqa: E402
    _booster_cost,  # noqa: E402
    compute_network_capex,
    mt_yr_to_kg_s,
)
from src.core.capex import _diameter as _module_diameter  # noqa: E402

_NEUTRAL_CELL = (1.0, 1.0, 1.0, 1.0, 0, 1000.0)  # comet_cell_cost = 1 → summation = 1·L


def test_mt_yr_to_kg_s_is_continuous():
    assert mt_yr_to_kg_s(1.0) == pytest.approx(1e9 / 31_557_600.0)  # 1 Mt/yr ≈ 31.69 kg/s
    assert mt_yr_to_kg_s(3.0) == pytest.approx(3 * mt_yr_to_kg_s(1.0))


def test_diameter_grows_with_flow():
    eng = _eng()
    assert _module_diameter(mt_yr_to_kg_s(5.0), eng) > _module_diameter(mt_yr_to_kg_s(2.0), eng)


def test_booster_cost_positive_and_scales_with_flow():
    eng = _eng()
    b_small = _booster_cost(mt_yr_to_kg_s(2.0), eng)
    b_big = _booster_cost(mt_yr_to_kg_s(5.0), eng)
    assert 0 < b_small < b_big


def test_network_edge_priced_by_its_own_flow():
    eng = _eng()
    spur = compute_network_capex([{"flow": 2.0, "junction": False, "values": [_NEUTRAL_CELL]}], eng, _nolog)
    trunk = compute_network_capex([{"flow": 5.0, "junction": False, "values": [_NEUTRAL_CELL]}], eng, _nolog)
    # Ip = Bc·D·(comet·L); D grows with flow → the trunk segment costs more than the spur.
    assert trunk["I_total"] > spur["I_total"]
    assert trunk["I_total"] == pytest.approx(eng["Bc"] * _module_diameter(mt_yr_to_kg_s(5.0), eng) * 1000.0)


def test_junction_adds_one_full_booster():
    eng = _eng()
    with_j = compute_network_capex([{"flow": 5.0, "junction": True, "values": [_NEUTRAL_CELL]}], eng, _nolog)
    without = compute_network_capex([{"flow": 5.0, "junction": False, "values": [_NEUTRAL_CELL]}], eng, _nolog)
    assert with_j["n_junction_boosters"] == 1 and without["n_junction_boosters"] == 0
    # The only difference is one full booster sized by the merged (downstream) M.
    assert with_j["I_total"] - without["I_total"] == pytest.approx(_booster_cost(mt_yr_to_kg_s(5.0), eng))


def test_network_totals_over_two_spurs_and_a_trunk():
    eng = _eng()
    edges = [
        {"flow": 2.0, "junction": False, "values": [_NEUTRAL_CELL]},
        {"flow": 3.0, "junction": False, "values": [_NEUTRAL_CELL]},
        {"flow": 5.0, "junction": True, "values": [_NEUTRAL_CELL]},
    ]
    out = compute_network_capex(edges, eng, _nolog)
    expected_pipe = sum(eng["Bc"] * _module_diameter(mt_yr_to_kg_s(f), eng) * 1000.0 for f in (2.0, 3.0, 5.0))
    assert out["n_junction_boosters"] == 1
    assert out["I_total"] == pytest.approx(expected_pipe + _booster_cost(mt_yr_to_kg_s(5.0), eng))
