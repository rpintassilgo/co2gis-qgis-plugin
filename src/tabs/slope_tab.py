from typing import TYPE_CHECKING
from qgis.PyQt.QtWidgets import (
    QLabel, QComboBox, QLineEdit, QPushButton, QHBoxLayout, QFormLayout,
    QGroupBox, QTableWidget, QHeaderView, QSpinBox, QCheckBox, QTableWidgetItem
)
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsProject, QgsRasterLayer
from qgis import processing
from osgeo import gdal
import numpy as np
import os

from ..task_manager import run_in_background
from ..utils import select_output_file

if TYPE_CHECKING:
    from ..analysis_dialog import AnalysisDialog


def setup_slope_tab(dialog: 'AnalysisDialog', layout: QFormLayout):
    """Sets up the Slope tab."""
    createSlopeGroupBox = QGroupBox()
    createSlopeGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")
    createSlopeLayout = QFormLayout()

    createSlopeTitle = QLabel("Create Slope from DEM")
    createSlopeTitle.setAlignment(Qt.AlignCenter)
    createSlopeTitle.setStyleSheet("font-weight: bold; font-size: 12px;")
    createSlopeLayout.addRow(createSlopeTitle)

    dialog.demComboBox = QComboBox()
    createSlopeLayout.addRow(QLabel("Select DEM Layer:"), dialog.demComboBox)

    dialog.slopeRasterPath = QLineEdit()
    dialog.slopeRasterPath.setPlaceholderText("Choose output path for Slope Raster")
    dialog.slopeRasterBrowse = QPushButton("Browse")
    dialog.slopeRasterBrowse.clicked.connect(lambda: select_output_file(dialog.slopeRasterPath, "tif"))

    slopeFileLayout = QHBoxLayout()
    slopeFileLayout.addWidget(dialog.slopeRasterPath)
    slopeFileLayout.addWidget(dialog.slopeRasterBrowse)
    createSlopeLayout.addRow(slopeFileLayout)

    dialog.create_slope_button = QPushButton("Create Slope Raster from DEM")
    createSlopeLayout.addRow(dialog.create_slope_button)

    createSlopeGroupBox.setLayout(createSlopeLayout)
    layout.addWidget(createSlopeGroupBox)

    slopeCostsGroupBox = QGroupBox()
    slopeCostsGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")
    slopeCostsLayout = QFormLayout()

    slopeCostsTitle = QLabel("Create Slope Costs")
    slopeCostsTitle.setAlignment(Qt.AlignCenter)
    slopeCostsTitle.setStyleSheet("font-weight: bold; font-size: 12px;")
    slopeCostsLayout.addRow(slopeCostsTitle)

    dialog.slopeLayerComboBox = QComboBox()
    slopeCostsLayout.addRow(QLabel("Select Slope Layer:"), dialog.slopeLayerComboBox)

    slopeCostsLayout.addRow(QLabel("Define Slope Cost Intervals:"))

    dialog.slopeCostTable = QTableWidget()
    dialog.slopeCostTable.setColumnCount(4)
    dialog.slopeCostTable.setHorizontalHeaderLabels(["Min % Slope", "Max % Slope", "Cost", "No Upper Limit"])
    dialog.slopeCostTable.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    slopeCostsLayout.addRow(dialog.slopeCostTable)

    slopeTableButtonsLayout = QHBoxLayout()
    dialog.addSlopeRowButton = QPushButton("Add Row")
    dialog.removeSlopeRowButton = QPushButton("Remove Selected Row")
    dialog.slopePopulateCometButton = QPushButton("Populate according to COMET")
    slopeTableButtonsLayout.addWidget(dialog.addSlopeRowButton)
    slopeTableButtonsLayout.addWidget(dialog.removeSlopeRowButton)
    slopeTableButtonsLayout.addWidget(dialog.slopePopulateCometButton)
    slopeCostsLayout.addRow(slopeTableButtonsLayout)

    dialog.slopeCostsRasterPath = QLineEdit()
    dialog.slopeCostsRasterPath.setPlaceholderText("Choose output path for Slope Costs Raster")
    dialog.slopeCostsRasterBrowse = QPushButton("Browse")
    dialog.slopeCostsRasterBrowse.clicked.connect(lambda: select_output_file(dialog.slopeCostsRasterPath, "tif"))

    slopeCostsFileLayout = QHBoxLayout()
    slopeCostsFileLayout.addWidget(dialog.slopeCostsRasterPath)
    slopeCostsFileLayout.addWidget(dialog.slopeCostsRasterBrowse)
    slopeCostsLayout.addRow(slopeCostsFileLayout)

    dialog.create_slope_costs_button = QPushButton("Create Slope Costs Raster")
    slopeCostsLayout.addRow(dialog.create_slope_costs_button)

    slopeCostsGroupBox.setLayout(slopeCostsLayout)
    layout.addWidget(slopeCostsGroupBox)

    setup_slope_cost_table_logic(dialog)


def connect_slope_signals(dialog: 'AnalysisDialog'):
    """Connects signals for the Slope tab."""
    dialog.create_slope_button.clicked.connect(lambda checked: run_in_background(dialog, run_slope_creation))
    dialog.create_slope_costs_button.clicked.connect(lambda checked: run_in_background(dialog, run_slope_costs_creation))


def _get_layer_id_from_widget(widget):
    """Helper to get layer ID from a QComboBox."""
    if not widget.currentData():
        raise ValueError(f"No layer selected in {widget.objectName()}.")
    return widget.currentData()


def run_slope_creation(dialog: 'AnalysisDialog'):
    """Create Slope Raster from DEM"""
    try:
        dem_layer = QgsProject.instance().mapLayer(_get_layer_id_from_widget(dialog.demComboBox))
        output_path = dialog.slopeRasterPath.text()

        if not dem_layer:
            raise ValueError("No DEM layer selected.")
        if not output_path:
            raise ValueError("No output path specified for Slope Raster.")

        dialog.log_message("Creating Slope Raster from DEM...", "Slope")
        create_slope_layer_from_dem(dem_layer, output_path)
        dialog.log_message(f"Slope Raster created at: {output_path}", "Slope")

        layer_name = os.path.splitext(os.path.basename(output_path))[0]
        slope_layer = QgsRasterLayer(output_path, layer_name)
        if slope_layer.isValid():
            QgsProject.instance().addMapLayer(slope_layer)
        else:
            dialog.log_message("Failed to load created slope layer.", "Slope")

    except Exception as e:
        dialog.log_message(f"Creating slope data failed: {e}", "Slope")


def run_slope_costs_creation(dialog: 'AnalysisDialog'):
    """Create slope costs raster based on defined intervals."""
    try:
        intervals = get_slope_cost_intervals(dialog)
        slope_layer = QgsProject.instance().mapLayer(dialog.slopeLayerComboBox.currentData())
        output_path = dialog.slopeCostsRasterPath.text()

        if not slope_layer:
            raise ValueError("No slope layer selected.")
        if not output_path:
            raise ValueError("No output path specified for Slope Costs Raster.")
        if not intervals:
            raise ValueError("No slope cost intervals defined.")

        dialog.log_message("Creating Slope Costs Raster...", "Slope")
        create_slope_costs_from_slope(slope_layer, intervals, output_path)
        dialog.log_message(f"Slope Costs Raster created successfully at: {output_path}", "Slope")

        layer_name = os.path.splitext(os.path.basename(output_path))[0]
        new_layer = QgsRasterLayer(output_path, layer_name)
        if new_layer.isValid():
            QgsProject.instance().addMapLayer(new_layer)
        else:
            dialog.log_message("Failed to load created slope costs layer.", "Slope")

    except Exception as e:
        dialog.log_message(f"Creating Slope Costs Raster Failed: {str(e)}", "Slope")


def get_slope_cost_intervals(dialog: 'AnalysisDialog'):
    """Extract slope intervals and costs from the table."""
    intervals = []
    for row in range(dialog.slopeCostTable.rowCount()):
        min_spin = dialog.slopeCostTable.cellWidget(row, 0)
        max_spin = dialog.slopeCostTable.cellWidget(row, 1)
        cost_item = dialog.slopeCostTable.item(row, 2)
        no_limit_checkbox = dialog.slopeCostTable.cellWidget(row, 3)

        min_val = min_spin.value()
        max_val = max_spin.value() if not no_limit_checkbox.isChecked() else None

        cost_text = cost_item.text() if cost_item else "1.0"
        try:
            cost = float(cost_text)
        except (ValueError, TypeError):
            cost = 1.0  # Default value if parsing fails
            dialog.log_message(f"Invalid cost value '{cost_text}' in row {row + 1}. Using default 1.0.", "Slope")

        intervals.append({"min": min_val, "max": max_val, "cost": cost})

    return intervals


def setup_slope_cost_table_logic(dialog: 'AnalysisDialog'):
    """Connects buttons to their functions for the slope cost table."""
    dialog.addSlopeRowButton.clicked.connect(lambda: add_slope_row(dialog))
    dialog.removeSlopeRowButton.clicked.connect(lambda: remove_selected_slope_row(dialog))
    dialog.slopePopulateCometButton.clicked.connect(lambda: populate_slope_table_with_comet_defaults(dialog))

    add_slope_row(dialog)  # Add a single empty row to start


def populate_slope_table_with_comet_defaults(dialog: 'AnalysisDialog'):
    """Clear the table and populate with COMET project default slope costs."""
    dialog.slopeCostTable.setRowCount(0)

    comet_defaults = [
        (0, 10, 1.0, False),
        (10, 20, 1.1, False),
        (20, 30, 1.2, False),
        (30, 70, 3.0, False),
        (70, 0, 9.0, True)
    ]
    for min_val, max_val, cost, no_limit in comet_defaults:
        add_slope_row(dialog, min_val, max_val, cost, no_limit)


def add_slope_row(dialog: 'AnalysisDialog', min_val=None, max_val=None, cost_val=None, no_limit=False):
    """Add a new row to the slope cost table."""
    row_position = dialog.slopeCostTable.rowCount()
    dialog.slopeCostTable.insertRow(row_position)

    min_spin = QSpinBox()
    min_spin.setRange(0, 1000)
    if min_val is not None:
        min_spin.setValue(min_val)
    dialog.slopeCostTable.setCellWidget(row_position, 0, min_spin)

    max_spin = QSpinBox()
    max_spin.setRange(0, 1000)
    if max_val is not None:
        max_spin.setValue(max_val)
    dialog.slopeCostTable.setCellWidget(row_position, 1, max_spin)

    cost_item = QTableWidgetItem(str(cost_val) if cost_val is not None else "1.0")
    dialog.slopeCostTable.setItem(row_position, 2, cost_item)

    no_limit_checkbox = QCheckBox()
    no_limit_checkbox.setChecked(no_limit)
    dialog.slopeCostTable.setCellWidget(row_position, 3, no_limit_checkbox)

    def toggle_max_spin(state):
        is_disabled = state == Qt.Checked
        max_spin.setDisabled(is_disabled)
        if is_disabled:
            max_spin.setValue(0)

    no_limit_checkbox.stateChanged.connect(toggle_max_spin)
    toggle_max_spin(Qt.Checked if no_limit else Qt.Unchecked)


def remove_selected_slope_row(dialog: 'AnalysisDialog'):
    """Remove selected rows from the slope cost table."""
    selected_rows = set(idx.row() for idx in dialog.slopeCostTable.selectedIndexes())
    for row in sorted(selected_rows, reverse=True):
        dialog.slopeCostTable.removeRow(row)


def create_slope_layer_from_dem(dem_layer: QgsRasterLayer, output_path: str):
    """Creates a slope raster from a DEM layer using the qgis:slope algorithm."""
    if not dem_layer:
        raise ValueError("Input DEM layer is not valid.")

    params = {
        'INPUT': dem_layer,
        'Z_FACTOR': 1,
        'UNITS': 1,  # Percent
        'OUTPUT': output_path
    }
    result = processing.run("qgis:slope", params)
    if not result or 'OUTPUT' not in result:
        raise RuntimeError("Slope processing failed to return the expected output.")
    return result['OUTPUT']


def create_slope_costs_from_slope(slope_layer: QgsRasterLayer, intervals: list, output_path: str):
    """Creates a slope cost raster from a slope layer and interval definitions."""
    # Open the input raster
    input_ds = gdal.Open(slope_layer.source())
    if not input_ds:
        raise RuntimeError("Could not open input raster with GDAL")

    # Read the input band
    band = input_ds.GetRasterBand(1)
    slope_data = band.ReadAsArray()

    # Create output array with same shape
    output_data = np.zeros_like(slope_data, dtype=np.float32)

    # Apply costs using numpy operations
    # First set the default cost for slopes above the last interval
    if intervals:
        output_data.fill(intervals[-1]['cost'])

    # Then apply each interval's cost
    for interval in reversed(intervals):  # Process in reverse to handle overlapping ranges correctly
        min_slope = interval['min']
        max_slope = interval['max']
        cost = interval['cost']

        # Create mask for values in this interval
        if max_slope is None:
            mask = slope_data >= min_slope
        else:
            mask = (slope_data >= min_slope) & (slope_data < max_slope)

        # Apply cost to masked areas
        output_data[mask] = cost

    # Create output raster
    driver = gdal.GetDriverByName('GTiff')
    out_ds = driver.Create(output_path,
                           input_ds.RasterXSize,
                           input_ds.RasterYSize,
                           1,
                           gdal.GDT_Float32,
                           options=['COMPRESS=LZW', 'NUM_THREADS=ALL_CPUS', 'BIGTIFF=YES'])

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
    layer_name = os.path.splitext(os.path.basename(output_path))[0]
    new_layer = QgsRasterLayer(output_path, layer_name)
    if new_layer.isValid():
        QgsProject.instance().addMapLayer(new_layer)
    else:
        raise RuntimeError("Failed to load the created Slope Costs raster.")
