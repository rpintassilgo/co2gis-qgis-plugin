from typing import TYPE_CHECKING, Union
from PyQt5.QtWidgets import QTableWidgetItem
from qgis.core import QgsProject, QgsRasterLayer, QgsPalettedRasterRenderer
from PyQt5.QtCore import Qt

if TYPE_CHECKING:
    from . import StepByStepDialog

def populate_land_use_classes_table(dialog: 'StepByStepDialog'):
    """Populates the table with unique land use classes from the selected raster's symbology."""
    dialog.classTable.setRowCount(0)

    layer_id = dialog.terrainComboBox.currentData()
    if not layer_id:
        return

    terrain_layer = QgsProject.instance().mapLayer(layer_id)
    if not isinstance(terrain_layer, QgsRasterLayer):
        dialog.log_message("Selected layer is not a valid raster layer.")
        return

    renderer = terrain_layer.renderer()
    if not isinstance(renderer, QgsPalettedRasterRenderer):
        dialog.log_message("Selected layer does not use a Paletted/Unique Values renderer. Cannot extract class names.")
        # Fallback to unique values if not paletted, though this won't have names.
        provider = terrain_layer.dataProvider()
        unique_values = provider.uniqueValues(1)
        for value in sorted(list(unique_values)):
            row_position = dialog.classTable.rowCount()
            dialog.classTable.insertRow(row_position)
            item_id = QTableWidgetItem(str(int(value)))
            dialog.classTable.setItem(row_position, 0, item_id)
            item_name = QTableWidgetItem("N/A")
            dialog.classTable.setItem(row_position, 1, item_name)
            item_cost = QTableWidgetItem("1.0")
            dialog.classTable.setItem(row_position, 2, item_cost)
        return

    classes = renderer.classes()
    if not classes:
        dialog.log_message("No class data available in the renderer.")
        return

    for entry in classes:
        row_position = dialog.classTable.rowCount()
        dialog.classTable.insertRow(row_position)
        
        # Class ID
        class_id_item = QTableWidgetItem(str(entry.value))
        class_id_item.setFlags(class_id_item.flags() ^ Qt.ItemIsEditable)
        dialog.classTable.setItem(row_position, 0, class_id_item)
        
        # Class Name
        class_name_item = QTableWidgetItem(entry.label)
        class_name_item.setFlags(class_name_item.flags() ^ Qt.ItemIsEditable)
        dialog.classTable.setItem(row_position, 1, class_name_item)

        # Default Cost
        cost_item = QTableWidgetItem("1.0")
        cost_item.setFlags(cost_item.flags() | Qt.ItemIsEditable)
        dialog.classTable.setItem(row_position, 2, cost_item)

    dialog.log_message(f"{len(classes)} land use classes loaded from layer style.") 