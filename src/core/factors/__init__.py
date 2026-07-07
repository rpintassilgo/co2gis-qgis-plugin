"""COMET cost-factor builders — one module per factor.

Each module turns its inputs into a single cost-factor raster used by the COMET
formula: Land Use (Flu), Slope (Fs), Corridors (Fc), Crossings (Fci) plus the
crossings count (N). Grouped here because they form one cohesive step (1:1 with
the four cost tabs); the formula that *combines* them lives in ``core/comet.py``.
"""
