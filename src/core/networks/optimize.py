"""Network optimization seam.

Level 1 does no optimization: the independent star already *is* the network, so
:func:`optimize_network` is a passthrough. It is kept as a stable entry point so
Level 2 (heuristic trunk merge) and Level 3 (MILP selection) can slot in behind
the same name without touching callers.

Level 3 will solve a MILP to pick the cheapest sub-network (which edges, discrete
diameters, per-edge flows) subject to sink capacities and a capture target. That
needs a solver: HiGHS (via ``highspy``, MIT-licensed) is the intended engine and
is probed here as an OPTIONAL dependency — the plugin installs small and the
network feature still runs via the heuristic fallback when no solver is present.
Whether to keep HiGHS optional or require it is still an open decision.
"""

from __future__ import annotations

from typing import Iterable

from .model import Edge

try:
    import highspy  # noqa: F401  (availability probe only — not used yet)

    HAS_SOLVER = True
except ImportError:
    HAS_SOLVER = False


def optimize_network(edges: Iterable[Edge]) -> list[Edge]:
    """Return the edges to build.

    Level 1: passthrough — the independent star is the network as-is. Levels 2/3
    replace the body (heuristic trunk merge / MILP) behind this same signature.
    """
    return list(edges)
