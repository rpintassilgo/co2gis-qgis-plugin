"""COMET cost-model constants shared by the routing surface and the CAPEX estimate.

Keeping these here (rather than as literals in lcp_tab / price_estimation_tab)
guarantees the routing surface and the cost estimate cannot silently drift apart.
"""

# Maximum number of co-located infrastructures per cell. Capping N keeps the
# COMET formula stable; both the routing surface and the CAPEX summation apply it.
N_CAP = 10

# Minimum cell cost written to the routing surface. r.drain needs strictly
# positive costs, so the combined raster is floored at this value.
COST_FLOOR = 0.001
