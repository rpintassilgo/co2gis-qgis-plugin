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


def populate_layer_dropdowns(dialog: "AnalysisDialog"):
    """Populate all dropdowns with available layers."""
    # ... (code from dropdowns.py)
    # Clear all dropdowns first
    dialog.landUseComboBox.clear()
    dialog.demComboBox.clear()
    dialog.combineLandUseDropdown.clear()
    dialog.combineSlopeDropdown.clear()
    dialog.combineCorridorsDropdown.clear()
    dialog.combineCrossingsDropdown.clear()
    dialog.combineNRasterDropdown.clear()
    dialog.clipRasterInputDropdown.clear()
    dialog.lcpInputDropdown.clear()
    dialog.pointsComboBox.clear()
    dialog.clipPointVectorComboBox.clear()
    dialog.resampleRasterComboBox.clear()
    dialog.vectorComboBox.clear()
    dialog.vector2ComboBox.clear()
    dialog.slopeLayerComboBox.clear()

    # Price estimation dropdowns
    dialog.pipelineVectorDropdown.clear()
    dialog.landUseCostsDropdown.clear()
    dialog.slopeCostsDropdown.clear()
    dialog.corridorsCostsDropdown.clear()
    dialog.crossingsCostsDropdown.clear()
    dialog.crossingsVectorDropdown.clear()

    # New crossings/corridors combo boxes
    dialog.crossingComboBox.clear()
    dialog.crossingRefRasterComboBox.clear()
    dialog.nCrossingVectorComboBox.clear()
    dialog.nCrossingRefRasterComboBox.clear()
    dialog.corridorComboBox.clear()
    dialog.corridorRefRasterComboBox.clear()

    # Get all layers from the project
    layers = QgsProject.instance().mapLayers().values()

    # Populate dropdowns based on layer type
    for layer in layers:
        if isinstance(layer, QgsRasterLayer):
            # Add to raster dropdowns
            dialog.landUseComboBox.addItem(layer.name(), layer.id())
            dialog.demComboBox.addItem(layer.name(), layer.id())
            dialog.combineLandUseDropdown.addItem(layer.name(), layer.id())
            dialog.combineSlopeDropdown.addItem(layer.name(), layer.id())
            dialog.combineCorridorsDropdown.addItem(layer.name(), layer.id())
            dialog.combineCrossingsDropdown.addItem(layer.name(), layer.id())
            dialog.combineNRasterDropdown.addItem(layer.name(), layer.id())
            dialog.clipRasterInputDropdown.addItem(layer.name(), layer.id())
            dialog.lcpInputDropdown.addItem(layer.name(), layer.id())
            dialog.resampleRasterComboBox.addItem(layer.name(), layer.id())
            dialog.slopeLayerComboBox.addItem(layer.name(), layer.id())
            # Price estimation raster dropdowns
            dialog.landUseCostsDropdown.addItem(layer.name(), layer.id())
            dialog.slopeCostsDropdown.addItem(layer.name(), layer.id())
            dialog.corridorsCostsDropdown.addItem(layer.name(), layer.id())
            dialog.crossingsCostsDropdown.addItem(layer.name(), layer.id())
            dialog.crossingRefRasterComboBox.addItem(layer.name(), layer.id())
            dialog.nCrossingRefRasterComboBox.addItem(layer.name(), layer.id())
            dialog.corridorRefRasterComboBox.addItem(layer.name(), layer.id())
        elif isinstance(layer, QgsVectorLayer):
            # Add to vector dropdowns
            if layer.geometryType() == QgsWkbTypes.PointGeometry:
                dialog.pointsComboBox.addItem(layer.name(), layer.id())
                dialog.clipPointVectorComboBox.addItem(layer.name(), layer.id())
            elif layer.geometryType() == QgsWkbTypes.LineGeometry:
                dialog.pipelineVectorDropdown.addItem(layer.name(), layer.id())
            dialog.vectorComboBox.addItem(layer.name(), layer.id())
            dialog.vector2ComboBox.addItem(layer.name(), layer.id())
            dialog.crossingComboBox.addItem(layer.name(), layer.id())
            dialog.nCrossingVectorComboBox.addItem(layer.name(), layer.id())
            dialog.corridorComboBox.addItem(layer.name(), layer.id())
            dialog.crossingsVectorDropdown.addItem(layer.name(), layer.id())

    # Logging messages if no layers are found
    if dialog.pointsComboBox.count() == 0:
        dialog.log_message("No point vector layers found.", "System")
    if dialog.demComboBox.count() == 0:
        dialog.log_message("No raster layers found for DEM.", "System")
    if dialog.landUseComboBox.count() == 0:
        dialog.log_message("No raster layers found for Land Use.", "System")
    if dialog.combineLandUseDropdown.count() == 0:
        dialog.log_message("No raster layers found for Land Use Costs Raster.", "System")
    if dialog.combineSlopeDropdown.count() == 0:
        dialog.log_message("No raster layers found for Slope Raster.", "System")
    if dialog.combineCorridorsDropdown.count() == 0:
        dialog.log_message("No raster layers found for Corridors Costs Raster.", "System")
    if dialog.combineCrossingsDropdown.count() == 0:
        dialog.log_message("No raster layers found for Crossings Costs Raster.", "System")
    if dialog.clipRasterInputDropdown.count() == 0:
        dialog.log_message("No raster layers found for clipping.", "System")
    if dialog.lcpInputDropdown.count() == 0:
        dialog.log_message("No raster layers found for least cost path calculation.", "System")
    if dialog.resampleRasterComboBox.count() == 0:
        dialog.log_message("No raster layers found for resampling.", "System")


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


def update_original_resolution(dialog: "AnalysisDialog"):
    """Update the original resolution input field based on the selected raster."""
    raster_layer = layer_from_dropdown(dialog.resampleRasterComboBox)
    if raster_layer:
        crs = raster_layer.crs()
        resolution_x = raster_layer.rasterUnitsPerPixelX()
        resolution_y = raster_layer.rasterUnitsPerPixelY()

        avg_resolution = round((resolution_x + resolution_y) / 2, 2)
        unit = "m" if crs.mapUnits() == QgsUnitTypes.DistanceMeters else "°"
        dialog.originalResolutionInput.setText(f"~{avg_resolution} {unit}")


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
