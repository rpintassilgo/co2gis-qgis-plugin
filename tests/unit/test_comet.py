"""Unit tests for the COMET per-cell cost factor (``src/core/comet.py``).

Pure NumPy math — no QGIS required. The COMET factor is
``Fc · Fs · [Flu·(1 − 0.1N) + 0.1N·Fci]`` with ``N`` capped at ``N_CAP``.
"""

import numpy as np

from src.constants.comet import N_CAP
from src.core.comet import comet_cell_cost


def test_all_neutral_factors_give_one():
    # Every factor at the 1.0 baseline and no crossings → neutral unit cost.
    assert comet_cell_cost(1.0, 1.0, 1.0, 1.0, 0) == 1.0


def test_without_crossings_bracket_is_land_use():
    # N = 0 → the bracket collapses to Flu; result = Fc·Fs·Flu (Fci ignored).
    assert comet_cell_cost(2.0, 1.5, 1.1, 9.0, 0) == 2.0 * 1.5 * 1.1


def test_at_cap_bracket_is_crossing():
    # N = N_CAP (10) → (1 − 0.1N) = 0 and 0.1N = 1 → the bracket is just Fci.
    assert comet_cell_cost(1.0, 1.0, 1.3, 3.0, N_CAP) == 3.0


def test_N_is_capped_above_the_limit():
    # Any N above the cap must behave exactly like N == N_CAP.
    assert comet_cell_cost(1.2, 1.1, 1.4, 2.7, 50) == comet_cell_cost(1.2, 1.1, 1.4, 2.7, N_CAP)


def test_half_blend():
    # N = 5 → 0.5 land-use + 0.5 crossing in the bracket.
    expected = 1.0 * 1.0 * (2.0 * 0.5 + 0.5 * 4.0)
    assert comet_cell_cost(1.0, 1.0, 2.0, 4.0, 5) == expected


def test_multiplicative_prefactors():
    # Fc and Fs scale the whole expression.
    assert comet_cell_cost(0.9, 1.2, 1.0, 1.0, 0) == 0.9 * 1.2


def test_vectorised_over_arrays():
    # The routing surface passes NumPy arrays; the result is elementwise.
    Flu = np.array([1.0, 2.0, 1.8])
    out = comet_cell_cost(1.0, 1.0, Flu, 3.0, 0)
    assert np.array_equal(out, Flu)
