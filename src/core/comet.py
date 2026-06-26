"""The COMET cell cost model — the single source of truth for the formula.

Both the routing cost surface (``lcp_tab``) and the CAPEX estimate
(``price_estimation_tab``) call :func:`comet_cell_cost`, so the least-cost route
stays consistent with the cheapest route to build.
"""

import numpy as np

from ..constants.comet import N_CAP


def comet_cell_cost(Fc, Fs, Flu, Fci, N):
    """COMET per-cell cost factor: ``Fc · Fs · [Flu·(1−0.1N) + 0.1N·Fci]``.

    N is capped at :data:`~src.constants.comet.N_CAP` first. Works elementwise
    for plain scalars or NumPy arrays (the routing surface passes arrays, the
    CAPEX summation passes per-cell scalars).
    """
    N = np.minimum(N, N_CAP)
    return Fc * Fs * (Flu * (1 - 0.1 * N) + 0.1 * N * Fci)
