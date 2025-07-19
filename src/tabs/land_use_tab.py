from typing import TYPE_CHECKING
from PyQt5.QtWidgets import (
    QLabel, QComboBox, QTableWidget, QLineEdit, QPushButton, QHBoxLayout,
    QFormLayout, QHeaderView, QTableWidgetItem, QDialog, QVBoxLayout
)
from PyQt5.QtCore import Qt
from qgis.core import QgsProject, QgsRasterLayer, QgsPalettedRasterRenderer
from qgis import processing
from functools import partial

from ..task_manager import run_in_background
from ..utils import select_output_file
from osgeo import gdal
import numpy as np

if TYPE_CHECKING:
    from ..analysis_dialog import AnalysisDialog

def setup_land_use_tab(dialog: 'AnalysisDialog', layout: QFormLayout):
    """Sets up the Land Use tab."""
    layout.addRow(QLabel("Select Land Use Layer:"), dialog.landUseComboBox)
    
    dialog.landUseCostTable = QTableWidget()
    dialog.landUseCostTable.setColumnCount(3)
    dialog.landUseCostTable.setHorizontalHeaderLabels(["Class ID", "Class Name", "Cost"])
    dialog.landUseCostTable.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    layout.addRow(dialog.landUseCostTable)

    tableButtonsLayout = QHBoxLayout()
    dialog.showCometValuesButton = QPushButton("Show COMET Values")
    dialog.landUsePopulateCometButton = QPushButton("Populate according to COMET")
    dialog.landUsePopulateCometButton.setObjectName("populateCometButton")
    tableButtonsLayout.addWidget(dialog.showCometValuesButton)
    tableButtonsLayout.addWidget(dialog.landUsePopulateCometButton)
    layout.addRow(tableButtonsLayout)

    dialog.landUseCostsRasterPath = QLineEdit()
    dialog.landUseCostsRasterPath.setPlaceholderText("Choose output path for Land Use Costs Raster")
    dialog.landUseBrowse = QPushButton("Browse")
    dialog.landUseBrowse.clicked.connect(lambda: select_output_file(dialog.landUseCostsRasterPath, "tif"))
    
    outputFileLayout = QHBoxLayout()
    outputFileLayout.addWidget(dialog.landUseCostsRasterPath)
    outputFileLayout.addWidget(dialog.landUseBrowse)
    layout.addRow(outputFileLayout)

    dialog.create_land_use_costs_button = QPushButton("Create Land Use Costs Raster")
    layout.addRow(dialog.create_land_use_costs_button)

def connect_land_use_signals(dialog: 'AnalysisDialog'):
    """Connects signals for the Land Use tab."""
    dialog.landUseComboBox.currentIndexChanged.connect(
        lambda: on_land_use_layer_changed(dialog),
        Qt.QueuedConnection
    )
    dialog.create_land_use_costs_button.clicked.connect(
        lambda checked: run_in_background(dialog, run_land_use_cost_creation)
    )
    dialog.showCometValuesButton.clicked.connect(lambda: open_comet_values_dialog(dialog))

    populate_handler = partial(populate_land_use_table_with_comet_defaults, dialog)
    dialog.landUsePopulateCometButton.clicked.connect(populate_handler)

    dialog.log_message("Connection for 'Populate according to COMET' button has been established.", "Land Use")

def on_land_use_layer_changed(dialog: 'AnalysisDialog'):
    """Handles changes in the land use layer selection, populating the table."""
    populate_land_use_table(dialog, dialog.landUseComboBox.currentData())

def run_land_use_cost_creation(dialog: 'AnalysisDialog'):
    """Create Land Use Cost Raster"""
    try:
        land_use_layer = QgsProject.instance().mapLayer(dialog.landUseComboBox.currentData())
        class_costs = get_land_use_costs(dialog)
        
        if not land_use_layer:
            raise ValueError("No land use layer selected.")
        if not class_costs:
            raise ValueError("No class costs defined in the table. Please add costs.")

        output_path = dialog.landUseCostsRasterPath.text()
        if not output_path:
            raise ValueError("No output path specified for Land Use Costs Raster.")
        
        dialog.log_message("Creating Land Use Costs Raster...", "Land Use")
        create_land_use_cost_raster(dialog, land_use_layer, class_costs, output_path)
        dialog.log_message(f"Land Use Costs Raster created successfully at: {output_path}", "Land Use")
    except Exception as e:
        dialog.log_message(f"Land Use Cost Raster creation Failed: {str(e)}", "Land Use")

def get_land_use_costs(dialog: 'AnalysisDialog'):
    """Extracts land use class costs from the table."""
    costs = {}
    for row in range(dialog.landUseCostTable.rowCount()):
        try:
            class_id = float(dialog.landUseCostTable.item(row, 0).text())
            cost = float(dialog.landUseCostTable.item(row, 2).text())
            costs[class_id] = cost
        except (ValueError, AttributeError):
            continue 
    return costs

def create_land_use_cost_raster(dialog: 'AnalysisDialog', land_use_layer: QgsRasterLayer, class_costs: dict, output_path: str):
    """Creates a land use cost raster from a layer and a dictionary of costs."""    
    # Open the input raster
    input_ds = gdal.Open(land_use_layer.source())
    if not input_ds:
        raise RuntimeError("Could not open input raster with GDAL")
        
    # Read the input band
    band = input_ds.GetRasterBand(1)
    input_data = band.ReadAsArray()
    
    # Create output array with same shape
    output_data = np.zeros_like(input_data, dtype=np.float32)
    
    # Calculate max cost for undefined values
    max_cost = max(class_costs.values()) if class_costs else 0
    undefined_cost = max_cost + 1
    
    # Set undefined cost as default
    output_data.fill(undefined_cost)
    
    # Apply costs using numpy operations (much faster than pixel-by-pixel)
    for class_id, cost in class_costs.items():
        output_data[input_data == class_id] = cost
        
    # Create output raster
    driver = gdal.GetDriverByName('GTiff')
    out_ds = driver.Create(output_path, 
                          input_ds.RasterXSize, 
                          input_ds.RasterYSize, 
                          1, 
                          gdal.GDT_Float32,
                          options=['COMPRESS=LZW', 'NUM_THREADS=ALL_CPUS'])
    
    # Copy projection and geotransform
    out_ds.SetProjection(input_ds.GetProjection())
    out_ds.SetGeoTransform(input_ds.GetGeoTransform())
    
    # Write data
    out_band = out_ds.GetRasterBand(1)
    out_band.WriteArray(output_data)
    
    # Clean up
    out_ds = None
    input_ds = None
    
    # Load the result into QGIS
    new_layer = QgsRasterLayer(output_path, "Land Use Costs")
    if new_layer.isValid():
        QgsProject.instance().addMapLayer(new_layer)
    else:
        dialog.log_message("Failed to load the created Land Use Costs raster.", "Land Use")

def populate_land_use_table(dialog: 'AnalysisDialog', layer_id: str):
    """Populates the table with unique land use classes from the selected raster's symbology."""
    dialog.landUseCostTable.setRowCount(0)

    if not layer_id:
        return

    terrain_layer = QgsProject.instance().mapLayer(layer_id)
    if not isinstance(terrain_layer, QgsRasterLayer):
        dialog.log_message("Selected layer is not a valid raster layer.", "Land Use")
        return

    renderer = terrain_layer.renderer()
    if not isinstance(renderer, QgsPalettedRasterRenderer):
        dialog.log_message("Selected layer does not use a Paletted/Unique Values renderer.", "Land Use")
        return

    classes = renderer.classes()
    if not classes:
        dialog.log_message("No class data available in the renderer.", "Land Use")
        return

    for entry in classes:
        row_position = dialog.landUseCostTable.rowCount()
        dialog.landUseCostTable.insertRow(row_position)
        
        class_id_item = QTableWidgetItem(str(entry.value))
        class_id_item.setFlags(class_id_item.flags() ^ Qt.ItemIsEditable)
        dialog.landUseCostTable.setItem(row_position, 0, class_id_item)
        
        class_name_item = QTableWidgetItem(entry.label)
        class_name_item.setFlags(class_name_item.flags() ^ Qt.ItemIsEditable)
        dialog.landUseCostTable.setItem(row_position, 1, class_name_item)

        cost_item = QTableWidgetItem("1.0")
        cost_item.setFlags(cost_item.flags() | Qt.ItemIsEditable)
        dialog.landUseCostTable.setItem(row_position, 2, cost_item)

    dialog.log_message(f"{len(classes)} land use classes loaded from layer style.", "Land Use")

def get_unique_values_from_raster_renderer(renderer: QgsPalettedRasterRenderer):
    """Extracts unique values from a paletted raster renderer."""
    return [c.value for c in renderer.classes()]

def populate_land_use_table_with_comet_defaults(dialog: 'AnalysisDialog'):
    """
    Populates the land use cost table with values from the COMET project.
    This function performs a strict check to ensure the selected layer is
    compatible with COMET/COSC standards before populating.
    """
    try:
        layer_id = dialog.landUseComboBox.currentData()
        if not layer_id:
            dialog.log_message("Cannot populate: No land use layer selected.", "Land Use")
            return
        
        layer = QgsProject.instance().mapLayer(layer_id)
        if not isinstance(layer, QgsRasterLayer):
            dialog.log_message("Cannot populate: The selected layer is not a valid raster layer.", "Land Use")
            return

        renderer = layer.renderer()
        if not isinstance(renderer, QgsPalettedRasterRenderer):
            dialog.log_message("Cannot populate: The selected raster does not have a paletted (unique values) renderer.", "Land Use")
            return

        unique_values = get_unique_values_from_raster_renderer(renderer)
        comet_class_ids = {100, 211, 212, 213, 311, 312, 313, 321, 322, 323, 410, 420, 500, 610, 620}
        
        unique_values_as_int = {int(v) for v in unique_values}

        if not unique_values_as_int.intersection(comet_class_ids):
            dialog.log_message("Cannot populate: The selected land use layer must be a 'Carta de Ocupação do Solo Conjuntural' from Direção-Geral do Território.", "Land Use")
            return

        comet_costs = {
            100: 1.8, 211: 1.1, 212: 1.1, 213: 1.1,
            311: 1.3, 312: 1.3, 313: 1.3, 321: 1.3, 322: 1.3, 323: 1.3,
            410: 1.1, 420: 1.1, 500: 1.0, 610: 1.2, 620: 4.0
        }

        populated_count = 0
        for row in range(dialog.landUseCostTable.rowCount()):
            class_id_item = dialog.landUseCostTable.item(row, 0)
            cost_item = dialog.landUseCostTable.item(row, 2)
            
            if class_id_item and cost_item:
                try:
                    class_id = int(float(class_id_item.text()))
                    if class_id in comet_costs:
                        cost_item.setText(str(comet_costs[class_id]))
                        populated_count += 1
                except ValueError:
                    continue
        
        if populated_count > 0:
            dialog.log_message(f"Land use costs populated with COMET default values for {populated_count} classes.", "Land Use")
        else:
            dialog.log_message("A COMET-compatible layer was detected, but no matching class IDs were found in the table to update.", "Land Use")
            
    except Exception as e:
        dialog.log_message(f"An unexpected error occurred while populating COMET values: {e}", "Land Use")

def open_comet_values_dialog(parent_dialog):
    """Opens the dialog that displays the COMET values table."""
    dialog = CometValuesDialog(parent_dialog)
    dialog.exec_()

class CometValuesDialog(QDialog):
    """A dialog to display the COMET land use class costs."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("COMET Project - Land Use Cost Factors")
        self.setMinimumSize(800, 510)
        self.setStyleSheet("""
            QDialog { background-color: #2a2a2a; }
            QTableWidget {
                background-color: #3c3c3c;
                color: white;
                gridline-color: #5a5a5a;
                font-size: 12px;
            }
            QHeaderView::section {
                background-color: #4a4a4a;
                color: white;
                padding: 4px;
                border: 1px solid #5a5a5a;
                font-weight: bold;
            }
        """)

        layout = QVBoxLayout()
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Class ID", "Thematic Class", "COMET Land Use", "Cost Factor"])
        table.setEditTriggers(QTableWidget.NoEditTriggers)

        data = [
            ("100", "Artificializado", "Áreas urbanas e associadas", "1.8"),
            ("211", "Culturas anuais de outono/inverno", "Terras cultivadas", "1.1"),
            ("212", "Culturas anuais de primavera/verão", "", ""),
            ("213", "Outras áreas agrícolas", "", ""),
            ("311", "Sobreiro e Azinheira", "Florestas", "1.3"),
            ("312", "Eucalipto", "", ""),
            ("313", "Outras folhosas", "", ""),
            ("321", "Pinheiro bravo", "", ""),
            ("322", "Pinheiro manso", "", ""),
            ("323", "Outras resinosas", "", ""),
            ("410", "Matos", "Áreas áridas", "1.1"),
            ("420", "Vegetação herbácea espontânea", "", ""),
            ("500", "Superfícies sem vegetação", "Áreas não povoadas", "1.0"),
            ("610", "Zonas húmidas", "Zonas regularmente inundadas", "1.2"),
            ("620", "Água", "Corpos de água", "4.0"),
        ]

        table.setRowCount(len(data))
        for row, row_data in enumerate(data):
            for col, cell_data in enumerate(row_data):
                table.setItem(row, col, QTableWidgetItem(cell_data))

        table.setSpan(1, 2, 3, 1)
        table.setSpan(1, 3, 3, 1)
        table.setSpan(4, 2, 6, 1)
        table.setSpan(4, 3, 6, 1)
        table.setSpan(10, 2, 2, 1)
        table.setSpan(10, 3, 2, 1)
        
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)

        layout.addWidget(table)
        self.setLayout(layout)
