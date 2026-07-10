"""Structural tests for the layer-selection dropdowns.

Every dropdown that lets the user pick a project layer must be searchable and kept
in sync with the project. Both behaviours are driven by membership in
``DROPDOWN_REGISTRY`` (``src/utils/layers.py``):

- ``AnalysisDialog._make_all_dropdowns_searchable`` iterates the registry to apply
  :func:`make_searchable_dropdown` — a combo outside it is never made searchable.
- ``populate_layer_dropdowns`` iterates the registry to (re)fill each combo on
  ``layersAdded`` — a combo outside it never refreshes.

So "is this a searchable, synced layer dropdown?" reduces to "is it registered?".
The ground truth for *what is a layer dropdown* is independent of the registry: a
combo is a layer selector exactly when its current item is resolved to a project
layer via :func:`layer_from_dropdown`. This test enforces that every such combo is
registered — the invariant that a combo left out of the registry (as happened with
``corridorLandUseComboBox``) is caught here instead of shipping as a stale,
non-searchable dropdown.

Pure source scanning + a stubbed-Qt import — no running QGIS required.
"""

import re
from pathlib import Path

from src.utils.layers import DROPDOWN_REGISTRY

_REPO_ROOT = Path(__file__).resolve().parents[2]
_UI_DIR = _REPO_ROOT / "src" / "ui"

# Matches ``layer_from_dropdown(dialog.<name>`` — the call that resolves a combo's
# current selection to a QgsMapLayer, i.e. the signature of a layer dropdown.
_LAYER_DROPDOWN_CALL = re.compile(r"layer_from_dropdown\(\s*dialog\.([A-Za-z0-9_]+)")


def _combos_resolved_as_layers():
    """Every ``dialog.<combo>`` passed to ``layer_from_dropdown`` across the UI code."""
    found = {}
    for path in _UI_DIR.rglob("*.py"):
        for match in _LAYER_DROPDOWN_CALL.finditer(path.read_text(encoding="utf-8")):
            found.setdefault(match.group(1), path.relative_to(_REPO_ROOT))
    return found


def _registered_attrs():
    return {attr for attr, _kind, _warning in DROPDOWN_REGISTRY}


def test_every_layer_dropdown_is_registered():
    """A combo resolved via ``layer_from_dropdown`` must be in ``DROPDOWN_REGISTRY``,
    otherwise it is neither searchable nor kept in sync with the project."""
    registered = _registered_attrs()
    resolved = _combos_resolved_as_layers()

    missing = {name: src for name, src in resolved.items() if name not in registered}
    assert not missing, (
        "Layer dropdowns resolved via layer_from_dropdown but missing from "
        f"DROPDOWN_REGISTRY (so not searchable / not synced): {sorted(missing)}. "
        f"Add them to DROPDOWN_REGISTRY in src/utils/layers.py. Seen at: "
        f"{ {n: str(p) for n, p in missing.items()} }"
    )


def test_the_scan_actually_found_dropdowns():
    """Guard against the regex silently matching nothing (which would make the
    coverage assertion vacuously pass)."""
    assert len(_combos_resolved_as_layers()) >= 10


def test_registry_has_no_duplicate_attrs():
    """Each dropdown appears once — a dup means it is cleared/filled twice per refresh."""
    attrs = [attr for attr, _kind, _warning in DROPDOWN_REGISTRY]
    dupes = sorted({a for a in attrs if attrs.count(a) > 1})
    assert not dupes, f"Duplicate attrs in DROPDOWN_REGISTRY: {dupes}"


def test_registry_kinds_are_known():
    """Every registry entry declares a supported layer kind."""
    valid = {"raster", "vector", "point", "line"}
    bad = {attr: kind for attr, kind, _warning in DROPDOWN_REGISTRY if kind not in valid}
    assert not bad, f"Unknown dropdown kinds in DROPDOWN_REGISTRY: {bad}"
