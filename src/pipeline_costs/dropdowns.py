from typing import TYPE_CHECKING
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer
from PyQt5.QtWidgets import QComboBox

if TYPE_CHECKING:
    from ..pipeline_costs import PipelineCostsDialog

def populate_layer_costs_dropdowns(dialog: 'PipelineCostsDialog'):
    """Populate the dropdowns with all available layers in the project."""
    # Clear existing items
    dialog.pipelineVectorDropdown.clear()
    dialog.landUseCostsDropdown.clear()
    dialog.slopeCostsDropdown.clear()
    dialog.corridorsCostsDropdown.clear()
    dialog.crossingsCostsDropdown.clear()

    # Get all layers in the project
    layers = QgsProject.instance().mapLayers().values()

    for layer in layers:
        layer_name = layer.name()
        layer_id = layer.id()

        if isinstance(layer, QgsVectorLayer) and layer.geometryType() == 1:
            # Populate line string layers
            dialog.pipelineVectorDropdown.addItem(layer_name, layer_id)
        
        elif isinstance(layer, QgsRasterLayer):
            dialog.landUseCostsDropdown.addItem(layer_name, layer_id)
            dialog.slopeCostsDropdown.addItem(layer_name, layer_id)
            dialog.corridorsCostsDropdown.addItem(layer_name, layer_id)
            dialog.crossingsCostsDropdown.addItem(layer_name, layer_id)
    
    # Logging messages if no layers are found
    if dialog.pipelineVectorDropdown.count() == 0:
        dialog.log_message("No polyline vector layers found for Pipeline.")
    if dialog.landUseCostsDropdown.count() == 0:
        dialog.log_message("No raster layers found for Land Use Costs.")
    if dialog.slopeCostsDropdown.count() == 0:
        dialog.log_message("No raster layers found for Slope Costs.")
    if dialog.corridorsCostsDropdown.count() == 0:
        dialog.log_message("No raster layers found for Corridors Costs.")
    if dialog.crossingsCostsDropdown.count() == 0:
        dialog.log_message("No raster layers found for Crossings Costs.")