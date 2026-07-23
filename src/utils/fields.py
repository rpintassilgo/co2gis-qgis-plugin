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
        unit = "m" if crs.mapUnits() == QgsUnitTypes.DistanceUnit.DistanceMeters else "°"
        line_edit.setText(f"~{avg_resolution} {unit}")


def update_pipeline_length(dialog: "AnalysisDialog"):
    """Update the read-only length field with the total length of the ACTIVE route vector.

    Single mode → the pipeline vector; Network mode (experimental) → the network vector, so the field
    shows the total pipe built (the sum of all segments), not the single-mode pipeline's stale length.
    """
    network = dialog.network_mode_experimental and dialog.priceModeNetworkRadio.isChecked()
    dropdown = dialog.priceNetworkVectorDropdown if network else dialog.pipelineVectorDropdown
    label = "network" if network else "pipeline"

    dialog.log_message(f"Updating {label} length...", "Price Estimation")
    if dropdown.currentIndex() == -1:
        dialog.pipelineLengthInput.setText("")
        dialog.log_message(f"No {label} vector selected. Clearing length field.", "Price Estimation")
        return

    layer = QgsProject.instance().mapLayer(dropdown.currentData())
    if not isinstance(layer, QgsVectorLayer) or layer.geometryType() != QgsWkbTypes.GeometryType.LineGeometry:
        dialog.log_message(
            f"Selected layer '{layer.name() if layer else 'None'}' is not a valid line vector.", "Price Estimation"
        )
        dialog.pipelineLengthInput.setText("")
        return

    total_length = round(sum(f.geometry().length() for f in layer.getFeatures()), 2)
    dialog.pipelineLengthInput.setText(str(total_length))
    dialog.log_message(f"Total {label} length for '{layer.name()}': {total_length} m", "Price Estimation")
