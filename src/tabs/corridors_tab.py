from typing import TYPE_CHECKING
from PyQt5.QtWidgets import (
    QLabel, QComboBox, QLineEdit, QPushButton, QHBoxLayout, QFormLayout, QTableWidget, QHeaderView, QCheckBox
)
from PyQt5.QtCore import Qt
from qgis.core import QgsProject, QgsRasterLayer
from qgis import processing
from osgeo import gdal
import numpy as np

from ..task_manager import run_in_background
from ..utils import select_output_file

if TYPE_CHECKING:
    from ..analysis_dialog import AnalysisDialog

def setup_corridors_tab(dialog: 'AnalysisDialog', layout: QFormLayout):
    dialog.corridorComboBox = QComboBox()
    layout.addRow(QLabel("Select Corridor Vector:"), dialog.corridorComboBox)
    dialog.corridorRefRasterComboBox = QComboBox()
    layout.addRow(QLabel("Select Reference Raster:"), dialog.corridorRefRasterComboBox)

    dialog.corridorPresentOffshoreInput = QLineEdit()
    dialog.corridorPresentOffshoreInput.setPlaceholderText("Cost for corridor present offshore")
    dialog.corridorPresentOffshoreInput.setText("2.7")
    layout.addRow(QLabel("Cost for corridor present offshore:"), dialog.corridorPresentOffshoreInput)

    dialog.corridorPresentOnshoreInput = QLineEdit()
    dialog.corridorPresentOnshoreInput.setPlaceholderText("Cost for corridor present onshore")
    dialog.corridorPresentOnshoreInput.setText("0.9")
    layout.addRow(QLabel("Cost for corridor present onshore:"), dialog.corridorPresentOnshoreInput)

    dialog.corridorAbsentOffshoreInput = QLineEdit()
    dialog.corridorAbsentOffshoreInput.setPlaceholderText("Cost for corridor absent offshore")
    dialog.corridorAbsentOffshoreInput.setText("3")
    layout.addRow(QLabel("Cost for corridor absent offshore:"), dialog.corridorAbsentOffshoreInput)

    dialog.corridorAbsentOnshoreInput = QLineEdit()
    dialog.corridorAbsentOnshoreInput.setPlaceholderText("Cost for corridor absent onshore")
    dialog.corridorAbsentOnshoreInput.setText("1")
    layout.addRow(QLabel("Cost for corridor absent onshore:"), dialog.corridorAbsentOnshoreInput)

    dialog.corridorLandUseComboBox = QComboBox()
    layout.addRow(QLabel("Select Land Use Layer:"), dialog.corridorLandUseComboBox)

    dialog.corridorLandUseTable = QTableWidget()
    dialog.corridorLandUseTable.setColumnCount(3)
    dialog.corridorLandUseTable.setHorizontalHeaderLabels(["Class ID", "Class Name", "Water Body"])
    dialog.corridorLandUseTable.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    layout.addRow(dialog.corridorLandUseTable)

    dialog.corridorOutputPath = QLineEdit()
    dialog.corridorOutputPath.setPlaceholderText("Choose output path for Raster")
    dialog.corridorBrowse = QPushButton("Browse")
    dialog.corridorBrowse.clicked.connect(lambda: select_output_file(dialog.corridorOutputPath, "tif"))
    outputCorridorLayout = QHBoxLayout()
    outputCorridorLayout.addWidget(dialog.corridorOutputPath)
    outputCorridorLayout.addWidget(dialog.corridorBrowse)
    layout.addRow(outputCorridorLayout)
    dialog.runCreateRasterFromCorridorButton = QPushButton("Create Corridors Costs Raster")
    layout.addRow(dialog.runCreateRasterFromCorridorButton)

    # Populate corridorLandUseComboBox with raster layers
    for layer in QgsProject.instance().mapLayers().values():
        if isinstance(layer, QgsRasterLayer):
            dialog.corridorLandUseComboBox.addItem(layer.name(), layer.id())

    # Connect dropdown change to table population
    dialog.corridorLandUseComboBox.currentIndexChanged.connect(
        lambda: populate_corridor_land_use_table(dialog, dialog.corridorLandUseComboBox.currentData())
    )

    # Initial population if any layer is selected
    if dialog.corridorLandUseComboBox.count() > 0:
        populate_corridor_land_use_table(dialog, dialog.corridorLandUseComboBox.currentData())

def populate_corridor_land_use_table(dialog, layer_id):
    from qgis.core import QgsProject, QgsRasterLayer, QgsPalettedRasterRenderer
    from PyQt5.QtWidgets import QTableWidgetItem, QCheckBox
    from PyQt5.QtCore import Qt
    dialog.corridorLandUseTable.setRowCount(0)
    if not layer_id:
        return
    layer = QgsProject.instance().mapLayer(layer_id)
    if not isinstance(layer, QgsRasterLayer):
        return
    renderer = layer.renderer()
    if not hasattr(renderer, 'classes'):
        return
    classes = renderer.classes()
    for entry in classes:
        row_position = dialog.corridorLandUseTable.rowCount()
        dialog.corridorLandUseTable.insertRow(row_position)
        class_id_item = QTableWidgetItem(str(entry.value))
        class_id_item.setFlags(class_id_item.flags() ^ Qt.ItemIsEditable)
        dialog.corridorLandUseTable.setItem(row_position, 0, class_id_item)
        class_name_item = QTableWidgetItem(entry.label)
        class_name_item.setFlags(class_name_item.flags() ^ Qt.ItemIsEditable)
        dialog.corridorLandUseTable.setItem(row_position, 1, class_name_item)
        water_checkbox = QCheckBox()
        water_checkbox.setChecked(False)
        water_checkbox.setStyleSheet("margin-left:50%; margin-right:50%;")
        dialog.corridorLandUseTable.setCellWidget(row_position, 2, water_checkbox)

def connect_corridors_signals(dialog: 'AnalysisDialog'):
    """Connects signals for the Corridors tab."""
    dialog.runCreateRasterFromCorridorButton.clicked.connect(
        lambda checked: run_in_background(dialog, run_corridors_cost_creation)
    )

def run_corridors_cost_creation(dialog: 'AnalysisDialog'):
    """Create Corridors Cost Raster"""
    try:
        corridor_layer = QgsProject.instance().mapLayer(dialog.corridorComboBox.currentData())
        ref_layer = QgsProject.instance().mapLayer(dialog.corridorRefRasterComboBox.currentData())
        land_use_layer = QgsProject.instance().mapLayer(dialog.corridorLandUseComboBox.currentData())
        output_path = dialog.corridorOutputPath.text().strip()

        # Validate inputs
        if not corridor_layer:
            raise ValueError("No corridor vector layer selected.")
        if not ref_layer:
            raise ValueError("No reference raster layer selected.")
        if not land_use_layer:
            raise ValueError("No land use layer selected.")
        if not output_path:
            raise ValueError("No output path specified.")

        # Get costs from inputs
        try:
            present_offshore_cost = float(dialog.corridorPresentOffshoreInput.text())
            present_onshore_cost = float(dialog.corridorPresentOnshoreInput.text())
            absent_offshore_cost = float(dialog.corridorAbsentOffshoreInput.text())
            absent_onshore_cost = float(dialog.corridorAbsentOnshoreInput.text())
        except ValueError as e:
            raise ValueError("Invalid cost values. Please ensure all costs are valid numbers.")

        # Get water body information from table
        water_bodies = set()
        for row in range(dialog.corridorLandUseTable.rowCount()):
            class_id_item = dialog.corridorLandUseTable.item(row, 0)
            water_checkbox = dialog.corridorLandUseTable.cellWidget(row, 2)
            if class_id_item and water_checkbox and water_checkbox.isChecked():
                try:
                    water_bodies.add(float(class_id_item.text()))
                except ValueError:
                    continue

        if not water_bodies:
            dialog.log_message("Warning: No water bodies selected in the table.", "Corridors")

        dialog.log_message("Creating Corridors Costs Raster...", "Corridors")

        # Create temporary file path in the same directory as output
        import os
        temp_dir = os.path.dirname(output_path)
        temp_corridor_path = os.path.join(temp_dir, "temp_corridor.tif")

        # First create a raster with corridor presence (1) or absence (0)
        params = {
            'INPUT': corridor_layer,
            'EXTENT': ref_layer,
            'TR': ref_layer,  # Use reference raster for target resolution
            'BURN': 1,  # Burn value of 1 for corridors
            'INIT': 0,  # Initialize with 0 for non-corridor areas
            'ADD': False,  # Don't add to existing raster values
            'OUTPUT': temp_corridor_path
        }

        dialog.log_message(f"Running rasterization with parameters: {params}", "Corridors")
        
        result = processing.run("gdal:rasterize", params)

        if not result or 'OUTPUT' not in result:
            raise RuntimeError("Corridor rasterization failed to produce output.")

        if not os.path.exists(temp_corridor_path):
            raise RuntimeError(f"Temporary raster file was not created at: {temp_corridor_path}")

        # Now combine with land use to determine final costs
        corridor_ds = gdal.Open(temp_corridor_path)
        if not corridor_ds:
            raise RuntimeError(f"Could not open temporary corridor raster at: {temp_corridor_path}")

        land_use_ds = gdal.Open(land_use_layer.source())
        if not land_use_ds:
            raise RuntimeError(f"Could not open land use raster at: {land_use_layer.source()}")

        corridor_data = corridor_ds.GetRasterBand(1).ReadAsArray()
        land_use_data = land_use_ds.GetRasterBand(1).ReadAsArray()

        if corridor_data is None:
            raise RuntimeError("Failed to read corridor raster data")
        if land_use_data is None:
            raise RuntimeError("Failed to read land use raster data")

        # Create output array
        output_data = np.zeros_like(corridor_data, dtype=np.float32)

        # Apply costs based on corridor presence and water body status
        is_water = np.isin(land_use_data, list(water_bodies))
        
        # Where corridor is present (1)
        output_data[np.where((corridor_data == 1) & is_water)] = present_offshore_cost
        output_data[np.where((corridor_data == 1) & ~is_water)] = present_onshore_cost
        
        # Where corridor is absent (0)
        output_data[np.where((corridor_data == 0) & is_water)] = absent_offshore_cost
        output_data[np.where((corridor_data == 0) & ~is_water)] = absent_onshore_cost

        # Create output raster
        driver = gdal.GetDriverByName('GTiff')
        out_ds = driver.Create(output_path,
                             corridor_ds.RasterXSize,
                             corridor_ds.RasterYSize,
                             1,
                             gdal.GDT_Float32,
                             options=['COMPRESS=LZW', 'NUM_THREADS=ALL_CPUS'])

        if not out_ds:
            raise RuntimeError(f"Failed to create output raster at: {output_path}")

        # Copy projection and geotransform
        out_ds.SetProjection(corridor_ds.GetProjection())
        out_ds.SetGeoTransform(corridor_ds.GetGeoTransform())

        # Write data
        out_band = out_ds.GetRasterBand(1)
        out_band.WriteArray(output_data)

        # Clean up
        out_ds = None
        corridor_ds = None
        land_use_ds = None

        # Remove temporary file
        try:
            if os.path.exists(temp_corridor_path):
                os.remove(temp_corridor_path)
        except Exception as e:
            dialog.log_message(f"Warning: Could not remove temporary file: {e}", "Corridors")

        # Load the result into QGIS
        new_layer = QgsRasterLayer(output_path, "Corridors Costs")
        if new_layer.isValid():
            QgsProject.instance().addMapLayer(new_layer)
            dialog.log_message(f"Corridors Costs Raster created successfully at: {output_path}", "Corridors")
        else:
            raise RuntimeError("Failed to load the created Corridors Costs raster.")

    except Exception as e:
        dialog.log_message(f"Creating Corridors Costs Raster Failed: {str(e)}", "Corridors")
        # Log additional error details if available
        import traceback
        dialog.log_message(f"Error details: {traceback.format_exc()}", "Corridors") 