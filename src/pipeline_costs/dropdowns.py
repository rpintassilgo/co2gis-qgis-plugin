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

    dialog.pipelineVectorDropdown.currentIndexChanged.connect(lambda: update_pipeline_length(dialog))
    
    # Logging messages if no layers are found
    if dialog.pipelineVectorDropdown.count() == 0:
        dialog.log_message("No polyline vector layers found for Pipeline.")
    if dialog.landUseCostsDropdown.count() == 0:
        dialog.log_message("No raster layers found for Land Use Costs.")
    if dialog.slopeCostsDropdown.count() == 0:
        dialog.log_message("No raster layers found for Slope Costs.")

def update_pipeline_length(dialog: 'PipelineCostsDialog'):
    """Calculate the total length of the selected pipeline vector and update the input field."""
    selected_index = dialog.pipelineVectorDropdown.currentIndex()
    if selected_index == -1:
        dialog.pipelineLengthInput.setText("")
        return

    layer_id = dialog.pipelineVectorDropdown.currentData()
    layer = QgsProject.instance().mapLayer(layer_id)

    if not isinstance(layer, QgsVectorLayer):
        dialog.log_message("Selected layer is not a valid polyline vector.")
        return

    total_length = sum(f.geometry().length() for f in layer.getFeatures())
    rounded_length = str(round(total_length, 2))

    dialog.pipelineLengthInput.setText(rounded_length)
    dialog.log_message(f"Pipeline Length updated: {rounded_length} m")
