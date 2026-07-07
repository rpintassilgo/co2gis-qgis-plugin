"""Pipeline-network domain logic (dormant — not wired into the UI yet).

Evolves the single origin→destination routing into a many-to-many network of CO2
sources and sinks. Like the rest of ``src/core``, the pure pieces here (``model``)
avoid Qt/PyQGIS so they can be unit-tested off the UI thread; the routing layer
(added later) reuses the GRASS chain in ``src/core/lcp.py``.

Maturity levels: Level 1 links each source to its nearest sink as an independent
"star"; Level 2 merges overlapping paths into shared trunks; Level 3 selects the
minimum-cost sub-network with a MILP.
"""
