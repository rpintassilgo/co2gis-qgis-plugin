from typing import TYPE_CHECKING
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer, QgsPalettedRasterRenderer
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QComboBox, QTableWidget, 
    QTableWidgetItem, QLineEdit, QPushButton, QHBoxLayout, 
    QFormLayout, QHeaderView, QTextEdit, QTabWidget, QMessageBox
)

if TYPE_CHECKING:
    from .import Dialog
 
def populate_layer_dropdowns(dialog: 'Dialog'):
        """Populate the dropdowns with all available layers in the project."""
        # Clear existing items
        dialog.terrainComboBox.clear()
        dialog.demComboBox.clear()
        dialog.pointsComboBox.clear()

        # get all layers in the project
        layers = QgsProject.instance().mapLayers().values()

        for layer in layers:
            layer_name = layer.name()
            layer_id = layer.id()

            if isinstance(layer, QgsRasterLayer):
                dialog.terrainComboBox.addItem(layer_name, layer_id)
                dialog.demComboBox.addItem(layer_name, layer_id)

            elif isinstance(layer, QgsVectorLayer) and layer.geometryType() == 0:
                dialog.pointsComboBox.addItem(layer_name, layer_id)

        if dialog.terrainComboBox.count() == 0:
            dialog.log_message("No raster layers found for Terrain Occupancy.")
        if dialog.demComboBox.count() == 0:
            dialog.log_message("No raster layers found for DEM.")
        if dialog.pointsComboBox.count() == 0:
            dialog.log_message("No point vector layers found for Points.")
            
def refresh_layer_dropdown(combo_box: QComboBox, layer_type):
    """Refresh the given combo_box with all layers of the specified type in the QGIS project."""
    combo_box.blockSignals(True)  # block signals to avoid recursion
    combo_box.clear()
    layers = QgsProject.instance().mapLayers().values()
    for layer in layers:
        if isinstance(layer, layer_type):
            combo_box.addItem(layer.name(), layer.id())
       