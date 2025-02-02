from typing import TYPE_CHECKING, Union
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer, QgsPalettedRasterRenderer
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QComboBox, QTableWidget, 
    QTableWidgetItem, QLineEdit, QPushButton, QHBoxLayout, 
    QFormLayout, QHeaderView, QTextEdit, QTabWidget, QMessageBox
)
from PyQt5.QtCore import Qt

if TYPE_CHECKING:
    from .import Dialog
    from ..step_dialog import StepByStepDialog

def populate_land_use_classes_table(dialog: Union['Dialog', 'StepByStepDialog']):
    # Get the selected terrain layer
    layer_id = dialog.terrainComboBox.currentData()
    terrain_layer = QgsProject.instance().mapLayer(layer_id)
    if not isinstance(terrain_layer, QgsRasterLayer):
        dialog.log_message("Selected layer is not a valid raster layer.")
        return

    # Check if the current renderer is a Paletted Raster Renderer
    renderer = terrain_layer.renderer()
    if not isinstance(renderer, QgsPalettedRasterRenderer):
        dialog.log_message("Selected layer does not use a Paletted/Unique Values renderer.")
        return

    classes = renderer.classes()
    if not classes:
        dialog.log_message("No class data available in the renderer.")
        return

    # populate the land use classes table
    dialog.classTable.setRowCount(len(classes))
    for row, entry in enumerate(classes):
        class_id_item = QTableWidgetItem(str(entry.value))
        class_id_item.setFlags(class_id_item.flags() ^ Qt.ItemIsEditable)
        dialog.classTable.setItem(row, 0, class_id_item)

        class_name_item = QTableWidgetItem(entry.label)
        class_name_item.setFlags(class_name_item.flags() ^ Qt.ItemIsEditable)
        dialog.classTable.setItem(row, 1, class_name_item)

        cost_item = QTableWidgetItem("0.0")
        cost_item.setFlags(cost_item.flags() | Qt.ItemIsEditable)
        dialog.classTable.setItem(row, 2, cost_item)

    dialog.log_message("Classification data added to the table.")

def get_land_use_class_costs(dialog: Union['Dialog', 'StepByStepDialog']):
    class_costs = {}
    for row in range(dialog.classTable.rowCount()):
        #dialog.log_message(dialog.classTable.item(row, 0).text())
        class_id = dialog.classTable.item(row, 0).text()
        cost = float(dialog.classTable.item(row, 2).text())
        class_costs[class_id] = cost
    return class_costs