"""Helpers that populate read-only UI fields from a selected layer."""

from typing import TYPE_CHECKING

from qgis.core import QgsProject, QgsUnitTypes, QgsVectorLayer, QgsWkbTypes
from qgis.PyQt.QtWidgets import QComboBox, QLineEdit

if TYPE_CHECKING:
    from ..analysis_dialog import AnalysisDialog


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
