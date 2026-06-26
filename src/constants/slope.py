"""COMET slope cost interval defaults.

Each entry is (min_slope, max_slope, cost, no_limit): slope range in degrees and
the COMET cost factor (Fs). When ``no_limit`` is True the interval is open-ended
(max is ignored). Used by the Slope tab's "Populate according to COMET" button.
"""

# (min, max, cost, no_limit)
COMET_SLOPE_INTERVALS = [
    (0, 10, 1.0, False),
    (10, 20, 1.1, False),
    (20, 30, 1.2, False),
    (30, 70, 3.0, False),
    (70, 0, 9.0, True),
]
