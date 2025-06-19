from typing import TYPE_CHECKING
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer, QgsWkbTypes
from PyQt5.QtWidgets import QComboBox

if TYPE_CHECKING:
    from ..step_dialog import StepByStepDialog

def populate_layer_step_by_step_dropdowns(dialog: 'StepByStepDialog'):
    """Populate all dropdowns with available layers."""
    # Clear all dropdowns first
    dialog.terrainComboBox.clear()
    dialog.demComboBox.clear()
    dialog.step3LandUseDropdown.clear()
    dialog.step3SlopeDropdown.clear()
    dialog.step3CorridorsDropdown.clear()
    dialog.step3CrossingsDropdown.clear()
    dialog.step4Dropdown.clear()
    dialog.step5Dropdown.clear()
    dialog.pointsComboBox.clear()
    dialog.clipPointVectorComboBox.clear()
    dialog.resampleRasterComboBox.clear()
    dialog.vectorComboBox.clear()
    dialog.vector2ComboBox.clear()
    dialog.vectorRasterComboBox.clear()
    dialog.refRasterComboBox.clear()
    dialog.slopeLayerComboBox.clear()

    # Get all layers from the project
    layers = QgsProject.instance().mapLayers().values()

    # Populate dropdowns based on layer type
    for layer in layers:
        if isinstance(layer, QgsRasterLayer):
            # Add to raster dropdowns
            dialog.terrainComboBox.addItem(layer.name(), layer.id())
            dialog.demComboBox.addItem(layer.name(), layer.id())
            dialog.step3LandUseDropdown.addItem(layer.name(), layer.id())
            dialog.step3SlopeDropdown.addItem(layer.name(), layer.id())
            dialog.step3CorridorsDropdown.addItem(layer.name(), layer.id())
            dialog.step3CrossingsDropdown.addItem(layer.name(), layer.id())
            dialog.step4Dropdown.addItem(layer.name(), layer.id())
            dialog.step5Dropdown.addItem(layer.name(), layer.id())
            dialog.resampleRasterComboBox.addItem(layer.name(), layer.id())
            dialog.refRasterComboBox.addItem(layer.name(), layer.id())
            dialog.slopeLayerComboBox.addItem(layer.name(), layer.id())
        elif isinstance(layer, QgsVectorLayer):
            # Add to vector dropdowns
            if layer.geometryType() == QgsWkbTypes.PointGeometry:
                dialog.pointsComboBox.addItem(layer.name(), layer.id())
                dialog.clipPointVectorComboBox.addItem(layer.name(), layer.id())
            dialog.vectorComboBox.addItem(layer.name(), layer.id())
            dialog.vector2ComboBox.addItem(layer.name(), layer.id())
            dialog.vectorRasterComboBox.addItem(layer.name(), layer.id())

    # Logging messages if no layers are found
    if dialog.pointsComboBox.count() == 0:
        dialog.log_message("No point vector layers found.")
    if dialog.demComboBox.count() == 0:
        dialog.log_message("No raster layers found for DEM.")
    if dialog.terrainComboBox.count() == 0:
        dialog.log_message("No raster layers found for Land Use.")
    if dialog.step3LandUseDropdown.count() == 0:
        dialog.log_message("No raster layers found for Land Use Costs Raster.")
    if dialog.step3SlopeDropdown.count() == 0:
        dialog.log_message("No raster layers found for Slope Raster.")
    if dialog.step3CorridorsDropdown.count() == 0:
        dialog.log_message("No raster layers found for Corridors Costs Raster.")
    if dialog.step3CrossingsDropdown.count() == 0:
        dialog.log_message("No raster layers found for Crossings Costs Raster.")
    if dialog.step4Dropdown.count() == 0:
        dialog.log_message("No raster layers found for clipping.")
    if dialog.step5Dropdown.count() == 0:
        dialog.log_message("No raster layers found for least cost path calculation.")
    if dialog.resampleRasterComboBox.count() == 0:
        dialog.log_message("No raster layers found for resampling.")

