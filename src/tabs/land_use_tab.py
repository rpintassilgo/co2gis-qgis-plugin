from typing import TYPE_CHECKING
from PyQt5.QtWidgets import (
    QLabel, QComboBox, QTableWidget, QLineEdit, QPushButton, QHBoxLayout,
    QFormLayout, QHeaderView, QTableWidgetItem
)
from PyQt5.QtCore import Qt
from qgis.core import QgsProject, QgsRasterLayer, QgsPalettedRasterRenderer
from qgis import processing

from ..task_manager import run_analysis
from ..utils import select_output_file

if TYPE_CHECKING:
    from ..analysis_dialog import AnalysisDialog

def setup_land_use_tab(dialog: 'AnalysisDialog', layout: QFormLayout):
    """Sets up the Land Use tab."""
    dialog.terrainComboBox = QComboBox()
    layout.addRow(QLabel("Select Land Use Layer:"), dialog.terrainComboBox)

    dialog.classTable = QTableWidget()
    dialog.classTable.setColumnCount(3)
    dialog.classTable.setHorizontalHeaderLabels(["Class ID", "Class Name", "Cost"])
    dialog.classTable.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    layout.addRow(QLabel("Land Use Classes Costs:"))
    layout.addRow(dialog.classTable)
    
    dialog.costsRasterPath = QLineEdit()
    dialog.costsRasterPath.setPlaceholderText("Choose output path for Costs Raster")
    dialog.costsRasterBrowse = QPushButton("Browse")
    dialog.costsRasterBrowse.clicked.connect(lambda: select_output_file(dialog.costsRasterPath, "tif"))
    
    costsfileLayout = QHBoxLayout()
    costsfileLayout.addWidget(dialog.costsRasterPath)
    costsfileLayout.addWidget(dialog.costsRasterBrowse)
    layout.addRow(costsfileLayout)

    dialog.create_land_use_costs_button = QPushButton("Create Land Use Costs Raster")
    layout.addRow(dialog.create_land_use_costs_button)

def connect_land_use_signals(dialog: 'AnalysisDialog'):
    """Connects signals for the Land Use tab."""
    dialog.terrainComboBox.currentIndexChanged.connect(lambda: populate_land_use_classes_table(dialog))
    dialog.create_land_use_costs_button.clicked.connect(lambda: run_analysis(dialog, run_land_use_costs_creation))

def populate_land_use_classes_table(dialog: 'AnalysisDialog'):
    """Populates the table with unique land use classes from the selected raster's symbology."""
    dialog.classTable.setRowCount(0)

    layer_id = dialog.terrainComboBox.currentData()
    if not layer_id:
        return

    terrain_layer = QgsProject.instance().mapLayer(layer_id)
    if not isinstance(terrain_layer, QgsRasterLayer):
        dialog.log_message("Selected layer is not a valid raster layer.", "Land Use")
        return

    renderer = terrain_layer.renderer()
    if not isinstance(renderer, QgsPalettedRasterRenderer):
        dialog.log_message("Selected layer does not use a Paletted/Unique Values renderer. Getting unique values directly from raster...", "Land Use")
        
        data_provider = terrain_layer.dataProvider()
        unique_values_with_count = data_provider.uniqueValues(1)
        
        for value, _ in sorted(unique_values_with_count):
            row_position = dialog.classTable.rowCount()
            dialog.classTable.insertRow(row_position)
            item_id = QTableWidgetItem(str(int(value)))
            dialog.classTable.setItem(row_position, 0, item_id)
            item_name = QTableWidgetItem("N/A")
            dialog.classTable.setItem(row_position, 1, item_name)
            item_cost = QTableWidgetItem("1.0")
            dialog.classTable.setItem(row_position, 2, item_cost)
        
        dialog.log_message(f"Found {len(unique_values_with_count)} unique values in the raster.", "Land Use")
        return

    classes = renderer.classes()
    if not classes:
        dialog.log_message("No class data available in the renderer.", "Land Use")
        return

    for entry in classes:
        row_position = dialog.classTable.rowCount()
        dialog.classTable.insertRow(row_position)
        
        class_id_item = QTableWidgetItem(str(entry.value))
        class_id_item.setFlags(class_id_item.flags() ^ Qt.ItemIsEditable)
        dialog.classTable.setItem(row_position, 0, class_id_item)
        
        class_name_item = QTableWidgetItem(entry.label)
        class_name_item.setFlags(class_name_item.flags() ^ Qt.ItemIsEditable)
        dialog.classTable.setItem(row_position, 1, class_name_item)

        cost_item = QTableWidgetItem("1.0")
        cost_item.setFlags(cost_item.flags() | Qt.ItemIsEditable)
        dialog.classTable.setItem(row_position, 2, cost_item)

    dialog.log_message(f"{len(classes)} land use classes loaded from layer style.", "Land Use")

def get_land_use_costs(dialog: 'AnalysisDialog'):
    """Extracts land use class costs from the table."""
    costs = {}
    for row in range(dialog.classTable.rowCount()):
        class_id = int(dialog.classTable.item(row, 0).text())
        cost = float(dialog.classTable.item(row, 2).text())
        costs[class_id] = cost
    return costs

def run_land_use_costs_creation(dialog: 'AnalysisDialog'):
    """Create Land Use Costs Raster"""
    try:
        land_use_layer = QgsProject.instance().mapLayer(dialog.terrainComboBox.currentData())
        class_costs = get_land_use_costs(dialog)
        
        if not land_use_layer:
            raise ValueError("No land use layer selected.")
        if not class_costs:
            raise ValueError("No class costs defined in the table. Please add costs.")

        output_path = dialog.costsRasterPath.text()
        if not output_path:
            raise ValueError("No output path specified for Land Use Costs Raster.")
        
        dialog.log_message("Creating Land Use Costs Raster...", "Land Use")
        get_land_use_costs_raster(land_use_layer, class_costs, output_path)
        dialog.log_message(f"Land Use Costs Raster created successfully at: {output_path}", "Land Use")
    except Exception as e:
        error_message = f"Creating Land Use Costs Raster Has Failed: {str(e)}"
        dialog.log_message(error_message, "Land Use")

def build_raster_calculator_expression(land_use_layer, class_costs):
    expression_parts = []
    max_cost = max(class_costs.values())
    undefined_cost = max_cost + 1

    for class_id, cost in class_costs.items():
        expression_parts.append(f'("{land_use_layer.name()}@1" = {class_id}) * {cost}')

    combined_expression = " + ".join(expression_parts)

    undefined_conditions = " * ".join(
        [f'("{land_use_layer.name()}@1" != {class_id})' for class_id in class_costs]
    )
    
    final_expression = f"({combined_expression}) + (({undefined_conditions}) * {undefined_cost})"
    return final_expression

def get_land_use_costs_raster(land_use_layer, class_costs, output_path):
    expression = build_raster_calculator_expression(land_use_layer, class_costs)
    
    params = {
        'EXPRESSION': expression,
        'LAYERS': [land_use_layer],
        'CELLSIZE': 0, # Use reference layer's cell size
        'EXTENT': land_use_layer.extent(),
        'CRS': land_use_layer.crs(),
        'OUTPUT': output_path
    }

    try:
        result = processing.run("qgis:rastercalculator", params)
        if not result or 'OUTPUT' not in result:
            raise RuntimeError("Raster calculator failed to return the expected output.")
        return result['OUTPUT']
    except Exception as e:
        raise RuntimeError(f"Raster calculator failed: {str(e)}")
