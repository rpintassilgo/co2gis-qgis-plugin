"""Unit tests for the pure flow-accumulation helpers (``src/core/networks/trunks.py``).

Pure NumPy — no QGIS/GRASS. Covers path-cell masking and the flow summation that
turns overlapping source paths into aggregated-flow (the trunks).
"""

import numpy as np

from src.core.networks.trunks import accumulate_flow, path_mask


def test_path_mask_float_excludes_nodata_and_nan():
    arr = np.array([[1.0, np.nan], [0.0, 5.0]], dtype=np.float32)
    mask = path_mask(arr, nodata=0.0)  # 0.0 = off-path NoData, NaN excluded
    assert mask.tolist() == [[True, False], [False, True]]


def test_path_mask_without_nodata_keeps_non_nan():
    arr = np.array([[1.0, np.nan]], dtype=np.float32)
    assert path_mask(arr, nodata=None).tolist() == [[True, False]]


def test_path_mask_integer_all_true_without_nodata():
    arr = np.array([[1, 2, 3]], dtype=np.int32)
    assert path_mask(arr, nodata=None).tolist() == [[True, True, True]]


def test_accumulate_flow_sums_overlap_into_a_trunk():
    a = np.array([[True, True, False]])  # source A, flow 2.0
    b = np.array([[False, True, True]])  # source B, flow 3.0
    acc = accumulate_flow((1, 3), [(a, 2.0), (b, 3.0)])
    # cell 0: only A → 2; cell 1: A+B → 5 (the trunk); cell 2: only B → 3
    assert acc.tolist() == [[2.0, 5.0, 3.0]]


def test_accumulate_flow_empty_is_zeros():
    assert accumulate_flow((2, 2), []).tolist() == [[0.0, 0.0], [0.0, 0.0]]
