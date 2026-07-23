"""Layer access and dropdown population helpers."""

import os
from typing import TYPE_CHECKING

from qgis.core import QgsMapLayer, QgsProject, QgsRasterLayer, QgsVectorLayer, QgsWkbTypes
from qgis.PyQt.QtWidgets import QComboBox

if TYPE_CHECKING:
    from ..analysis_dialog import AnalysisDialog


def layer_from_dropdown(combo: QComboBox):
    """Return the map layer whose id is stored as the combo's current item data.

    Replaces the ``QgsProject.instance().mapLayer(<combo>.currentData())``
    pattern repeated across every tab. Returns ``None`` if nothing is selected
    or the layer is no longer in the project.
    """
    return QgsProject.instance().mapLayer(combo.currentData())


def load_raster_result(
    dialog: "AnalysisDialog",
    path: str,
    tab: str = None,
    msg: str = None,
    *,
    error: str = "Failed to load the resulting raster layer.",
):
    """Load a written raster into the project and (optionally) log a message.

    Replaces the ``splitext(basename(path))`` → ``QgsRasterLayer`` → ``isValid``
    guard → ``addMapLayer`` → ``log`` sequence copy-pasted across every tab's
    ``_*_publish``. Runs on the main thread (publish phase).

    :param path: the written raster path; its basename (sans extension) is the layer name.
    :param tab: log tab name; only used when ``msg`` is given.
    :param msg: optional success message logged via ``dialog.log_message(msg, tab)``.
    :param error: ``RuntimeError`` message raised when the layer fails to load.
    :returns: the loaded :class:`QgsRasterLayer` (so callers can copy symbology, etc.).
    """
    layer_name = os.path.splitext(os.path.basename(path))[0]
    layer = QgsRasterLayer(path, layer_name)
    if not layer.isValid():
        raise RuntimeError(error)
    QgsProject.instance().addMapLayer(layer)
    if msg:
        dialog.log_message(msg, tab)
    return layer


# Data-driven registry of every layer-selection dropdown.
#
# Each entry maps a dropdown attribute on the dialog to:
#   - kind: which layers it accepts. "raster" -> raster layers; "vector" -> any
#     vector layer; "point" -> point-geometry vectors; "line" -> line-geometry
#     vectors. (A point/line vector also matches "vector".)
#   - warning: the "no layers found" message logged when the dropdown ends up
#     empty, or None for dropdowns that never logged a warning.
#
# Ordering: warning-bearing entries come first, in the exact order their
# messages were emitted by the original hand-written code, so the System log
# output is identical.
DROPDOWN_REGISTRY = [
    ("pointsComboBox", "point", "No point vector layers found."),
    ("demComboBox", "raster", "No raster layers found for DEM."),
    ("landUseComboBox", "raster", "No raster layers found for Land Use."),
    ("combineLandUseDropdown", "raster", "No raster layers found for Land Use Costs Raster."),
    ("combineSlopeDropdown", "raster", "No raster layers found for Slope Raster."),
    ("combineCorridorsDropdown", "raster", "No raster layers found for Corridors Costs Raster."),
    ("combineCrossingsDropdown", "raster", "No raster layers found for Crossings Costs Raster."),
    ("clipRasterInputDropdown", "raster", "No raster layers found for clipping."),
    ("lcpInputDropdown", "raster", "No raster layers found for least cost path calculation."),
    ("resampleRasterComboBox", "raster", "No raster layers found for resampling."),
    # Remaining raster dropdowns (no warning).
    ("combineNRasterDropdown", "raster", None),
    ("slopeLayerComboBox", "raster", None),
    ("landUseCostsDropdown", "raster", None),
    ("slopeCostsDropdown", "raster", None),
    ("corridorsCostsDropdown", "raster", None),
    ("crossingsCostsDropdown", "raster", None),
    ("crossingRefRasterComboBox", "raster", None),
    ("nCrossingRefRasterComboBox", "raster", None),
    ("corridorRefRasterComboBox", "raster", None),
    ("corridorLandUseComboBox", "raster", None),
    # Point-geometry vector dropdowns.
    ("clipPointVectorComboBox", "point", None),
    ("networkSourcesDropdown", "point", None),
    ("networkSinksDropdown", "point", None),
    # Line-geometry vector dropdowns.
    ("pipelineVectorDropdown", "line", None),
    ("priceNetworkVectorDropdown", "line", None),
    # Any-geometry vector dropdowns.
    ("vectorComboBox", "vector", None),
    ("vector2ComboBox", "vector", None),
    ("crossingComboBox", "vector", None),
    ("nCrossingVectorComboBox", "vector", None),
    ("corridorComboBox", "vector", None),
    ("crossingsVectorDropdown", "vector", None),
]


def _layer_kinds(layer: QgsMapLayer) -> set:
    """Return the set of registry "kinds" a layer should populate."""
    if isinstance(layer, QgsRasterLayer):
        return {"raster"}
    if isinstance(layer, QgsVectorLayer):
        kinds = {"vector"}
        geometry_type = layer.geometryType()
        if geometry_type == QgsWkbTypes.GeometryType.PointGeometry:
            kinds.add("point")
        elif geometry_type == QgsWkbTypes.GeometryType.LineGeometry:
            kinds.add("line")
        return kinds
    return set()


def populate_layer_dropdowns(dialog: "AnalysisDialog"):
    """Populate all dropdowns with available layers."""
    # Clear all dropdowns first.
    for attr, _kind, _warning in DROPDOWN_REGISTRY:
        getattr(dialog, attr).clear()

    # Populate each dropdown with the layers matching its kind, in project order.
    for layer in QgsProject.instance().mapLayers().values():
        kinds = _layer_kinds(layer)
        if not kinds:
            continue
        for attr, kind, _warning in DROPDOWN_REGISTRY:
            if kind in kinds:
                getattr(dialog, attr).addItem(layer.name(), layer.id())

    # Log a warning for each empty dropdown that declares one.
    for attr, _kind, warning in DROPDOWN_REGISTRY:
        if warning and getattr(dialog, attr).count() == 0:
            dialog.log_message(warning, "System")


def get_layer_path(layer: QgsMapLayer):
    """Returns the file path of the given QgsMapLayer."""
    if layer is None:
        raise ValueError("Layer is None. Please check your selection.")

    data_provider = layer.dataProvider()
    if not data_provider:
        raise ValueError("Layer does not have a valid data provider.")

    uri = data_provider.dataSourceUri()

    if layer.type() == QgsMapLayer.LayerType.RasterLayer:
        return uri
    if layer.type() == QgsMapLayer.LayerType.VectorLayer:
        path = uri.split("|")[0]
        return os.path.abspath(path)

    raise ValueError("Unsupported layer type. Only Raster and Vector layers are supported.")
