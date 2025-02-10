from typing import TYPE_CHECKING
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer
from PyQt5.QtWidgets import QComboBox

if TYPE_CHECKING:
    from ..step_dialog import StepByStepDialog

def populate_layer_step_by_step_dropdowns(dialog: 'StepByStepDialog'):
    """Populate the dropdowns with all available layers in the project."""
    # Clear existing items
    dialog.pointsComboBox.clear()
    dialog.demComboBox.clear()
    dialog.terrainComboBox.clear()
    dialog.step3LandUseDropdown.clear()
    dialog.step3SlopeDropdown.clear()
    dialog.step4Dropdown.clear()
    dialog.step5Dropdown.clear()
    dialog.resampleRasterComboBox.clear()

    # Get all layers in the project
    layers = QgsProject.instance().mapLayers().values()

    for layer in layers:
        layer_name = layer.name()
        layer_id = layer.id()

        if isinstance(layer, QgsVectorLayer) and layer.geometryType() == 0:
            # Populate point layers (Step 1)
            dialog.pointsComboBox.addItem(layer_name, layer_id)
        
        elif isinstance(layer, QgsRasterLayer):
            # Populate DEM layers (Step 2)
            dialog.demComboBox.addItem(layer_name, layer_id)
            # Populate Land Use layers (Step 3)
            dialog.terrainComboBox.addItem(layer_name, layer_id)
            # Populate Combined Raster (Step 4)
            dialog.step3LandUseDropdown.addItem(layer_name, layer_id)
            dialog.step3SlopeDropdown.addItem(layer_name, layer_id)
            # Populate Select Combined Raster (Step 5)
            dialog.step4Dropdown.addItem(layer_name, layer_id)
            # Populate Select Clipped Combined Raster (Step 6)
            dialog.step5Dropdown.addItem(layer_name, layer_id)
            # Populate Select Clipped Combined Raster (Step 6)
            dialog.resampleRasterComboBox.addItem(layer_name, layer_id)

    # Logging messages if no layers are found
    if dialog.pointsComboBox.count() == 0:
        dialog.log_message("No point vector layers found for Start and End Points.")
    if dialog.demComboBox.count() == 0:
        dialog.log_message("No raster layers found for DEM.")
    if dialog.terrainComboBox.count() == 0:
        dialog.log_message("No raster layers found for Land Use.")
    if dialog.step3LandUseDropdown.count() == 0:
        dialog.log_message("No raster layers found for Land Use Costs Raster.")
    if dialog.step3SlopeDropdown.count() == 0:
        dialog.log_message("No raster layers found for Slope Raster.")
    if dialog.step4Dropdown.count() == 0:
        dialog.log_message("No raster layers found for Combined Raster.")
    if dialog.step5Dropdown.count() == 0:
        dialog.log_message("No raster layers found for Clipped Combined Raster.")

