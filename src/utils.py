import os
from typing import TYPE_CHECKING

from qgis.core import QgsMapLayer, QgsProject, QgsRasterLayer, QgsUnitTypes, QgsVectorLayer, QgsWkbTypes
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QComboBox, QCompleter, QFileDialog, QLineEdit

if TYPE_CHECKING:
    from .analysis_dialog import AnalysisDialog


def layer_from_dropdown(combo: QComboBox):
    """Return the map layer whose id is stored as the combo's current item data.

    Replaces the ``QgsProject.instance().mapLayer(<combo>.currentData())``
    pattern repeated across every tab. Returns ``None`` if nothing is selected
    or the layer is no longer in the project.
    """
    return QgsProject.instance().mapLayer(combo.currentData())


def grass_alg_id(name: str) -> str:
    """
    Resolve a GRASS processing algorithm id across QGIS versions.

    QGIS 3.x registers GRASS algorithms under the ``grass7:`` prefix; QGIS 4.x
    renamed the provider to ``grass:``. Probe the processing registry and return
    whichever prefix is actually available, preferring the modern ``grass:``
    form and falling back to it when neither is found.

    :param name: algorithm name without prefix, e.g. ``"r.cost"``.
    """
    from qgis.core import QgsApplication

    registry = QgsApplication.processingRegistry()
    for prefix in ("grass", "grass7"):
        alg_id = f"{prefix}:{name}"
        if registry.algorithmById(alg_id) is not None:
            return alg_id
    return f"grass:{name}"


def make_searchable_dropdown(dropdown: QComboBox):
    """
    Makes a QComboBox searchable with autocomplete filtering.
    User can type to filter options - matches anywhere in the text.
    """
    dropdown.setEditable(True)
    dropdown.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)  # Prevent adding new items

    # Configure completer for better search experience
    completer = dropdown.completer()
    if completer:
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)  # Match anywhere in text
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)  # Case-insensitive search


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
    # Point-geometry vector dropdowns.
    ("clipPointVectorComboBox", "point", None),
    # Line-geometry vector dropdowns.
    ("pipelineVectorDropdown", "line", None),
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
        if geometry_type == QgsWkbTypes.PointGeometry:
            kinds.add("point")
        elif geometry_type == QgsWkbTypes.LineGeometry:
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


def update_resolution_field(dialog: "AnalysisDialog", combo_box: QComboBox, line_edit: QLineEdit):
    """Update the resolution input field based on the selected raster."""
    layer_id = combo_box.currentData()
    if not layer_id:
        line_edit.setText("")
        return

    raster_layer = QgsProject.instance().mapLayer(layer_id)
    if raster_layer:
        crs = raster_layer.crs()
        resolution_x = raster_layer.rasterUnitsPerPixelX()
        resolution_y = raster_layer.rasterUnitsPerPixelY()
        avg_resolution = round((resolution_x + resolution_y) / 2, 2)
        unit = "m" if crs.mapUnits() == QgsUnitTypes.DistanceMeters else "°"
        line_edit.setText(f"~{avg_resolution} {unit}")


def update_pipeline_length(dialog: "AnalysisDialog"):
    """Calculate the total length of the selected pipeline vector and update the input field."""
    dialog.log_message("Updating pipeline length...", "Price Estimation")
    selected_index = dialog.pipelineVectorDropdown.currentIndex()
    if selected_index == -1:
        dialog.pipelineLengthInput.setText("")
        dialog.log_message("No pipeline vector selected. Clearing length field.", "Price Estimation")
        return

    layer_id = dialog.pipelineVectorDropdown.currentData()
    dialog.log_message(f"Selected pipeline layer ID: {layer_id}", "Price Estimation")
    layer = QgsProject.instance().mapLayer(layer_id)

    if not isinstance(layer, QgsVectorLayer) or layer.geometryType() != QgsWkbTypes.LineGeometry:
        dialog.log_message(
            f"Selected layer '{layer.name() if layer else 'None'}' is not a valid line vector.", "Price Estimation"
        )
        dialog.pipelineLengthInput.setText("")
        return

    total_length = sum(f.geometry().length() for f in layer.getFeatures())
    rounded_length = str(round(total_length, 2))

    dialog.pipelineLengthInput.setText(rounded_length)
    dialog.log_message(f"Entire pipeline length for '{layer.name()}' updated: {rounded_length} m", "Price Estimation")


def select_output_file(output_field: QLineEdit, file_type: str):
    """Open a file dialog to select an output file location."""
    file_dialog = QFileDialog()
    file_dialog.setFileMode(QFileDialog.FileMode.AnyFile)
    file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)

    if file_type == "tif":
        name_filter = "TIF files (*.tif)"
    elif file_type == "gpkg":
        name_filter = "GeoPackage files (*.gpkg)"
    elif file_type == "ogr":
        name_filter = "ESRI Shapefile (*.shp)"
    else:
        name_filter = f"*.{file_type}"

    file_dialog.setNameFilter(name_filter)

    if file_dialog.exec():
        selected_files = file_dialog.selectedFiles()
        if selected_files:
            selected_file = selected_files[0]
            # The dialog should handle the extension, but as a fallback:
            if not selected_file.lower().endswith(f".{file_type}") and file_type != "ogr":
                if not os.path.splitext(selected_file)[1]:
                    selected_file += f".{file_type}"
            output_field.setText(selected_file)


def get_layer_path(layer: QgsMapLayer):
    """Returns the file path of the given QgsMapLayer."""
    if layer is None:
        raise ValueError("Layer is None. Please check your selection.")

    data_provider = layer.dataProvider()
    if not data_provider:
        raise ValueError("Layer does not have a valid data provider.")

    uri = data_provider.dataSourceUri()

    if layer.type() == QgsMapLayer.RasterLayer:
        return uri
    if layer.type() == QgsMapLayer.VectorLayer:
        path = uri.split("|")[0]
        return os.path.abspath(path)

    raise ValueError("Unsupported layer type. Only Raster and Vector layers are supported.")


def apply_symbology(original_layer: QgsRasterLayer, clipped_layer: QgsRasterLayer):
    """Applies symbology from the original raster to the clipped raster."""
    if not original_layer or not clipped_layer:
        raise ValueError("Original layer or clipped layer is missing.")

    if not original_layer.isValid() or not clipped_layer.isValid():
        raise ValueError("One or both layers are invalid.")

    # Get the renderer from the original layer
    renderer = original_layer.renderer()
    if renderer:
        # Clone the renderer and apply to clipped layer
        clipped_layer.setRenderer(renderer.clone())
        clipped_layer.triggerRepaint()
    else:
        raise ValueError("Original layer has no renderer to copy.")
