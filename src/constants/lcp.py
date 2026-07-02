"""Constants for the LCP routing step (GRASS r.cost).

Data only — no Qt, no processing — so both the domain code (``src.core.lcp``) and the
UI (``src.ui.settings_dialog``) can share the same r.cost memory defaults/bounds.
"""

# QgsSettings key + bounds for the r.cost memory budget (MB).
RCOST_MEMORY_KEY = "least_cost_pipeline/rcost_memory_mb"
DEFAULT_RCOST_MEMORY_MB = 8000
MIN_RCOST_MEMORY_MB = 100
MAX_RCOST_MEMORY_MB = 64000
RCOST_MEMORY_STEP_MB = 512
