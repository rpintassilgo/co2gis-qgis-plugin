from typing import TYPE_CHECKING
from PyQt5.QtWidgets import (
    QLabel, QComboBox, QLineEdit, QPushButton, QHBoxLayout, QFormLayout
)
from PyQt5.QtCore import Qt
from qgis.core import QgsProject, QgsRasterLayer
from qgis import processing
from ..task_manager import run_in_background
from ..utils import select_output_file

if TYPE_CHECKING:
    from ..analysis_dialog import AnalysisDialog

def setup_crossings_tab(dialog: 'AnalysisDialog', layout: QFormLayout):
    dialog.crossingComboBox = QComboBox()
    layout.addRow(QLabel("Select Crossing Vector:"), dialog.crossingComboBox)
    dialog.crossingRefRasterComboBox = QComboBox()
    layout.addRow(QLabel("Select Reference Raster:"), dialog.crossingRefRasterComboBox)
    dialog.crossingCostInput = QLineEdit()
    dialog.crossingCostInput.setPlaceholderText("Enter cost where crossing is present")
    dialog.crossingCostInput.setText("3")
    layout.addRow(QLabel("Cost for crossing-covered cells:"), dialog.crossingCostInput)
    dialog.crossingNoCostInput = QLineEdit()
    dialog.crossingNoCostInput.setPlaceholderText("Enter cost where crossing is absent")
    dialog.crossingNoCostInput.setText("1")
    layout.addRow(QLabel("Cost for non-crossing cells:"), dialog.crossingNoCostInput)
    dialog.crossingOutputPath = QLineEdit()
    dialog.crossingOutputPath.setPlaceholderText("Choose output path for Raster")
    dialog.crossingBrowse = QPushButton("Browse")
    dialog.crossingBrowse.clicked.connect(lambda: select_output_file(dialog.crossingOutputPath, "tif"))
    outputCrossingLayout = QHBoxLayout()
    outputCrossingLayout.addWidget(dialog.crossingOutputPath)
    outputCrossingLayout.addWidget(dialog.crossingBrowse)
    layout.addRow(outputCrossingLayout)
    dialog.runCreateRasterFromCrossingButton = QPushButton("Create Crossings Costs Raster")
    layout.addRow(dialog.runCreateRasterFromCrossingButton)

def connect_crossings_signals(dialog: 'AnalysisDialog'):
    """Connects signals for the Crossings tab."""
    dialog.runCreateRasterFromCrossingButton.clicked.connect(
        lambda: run_in_background(dialog, lambda: run_crossings_cost_creation(dialog))
    )

def run_crossings_cost_creation(dialog: 'AnalysisDialog'):
    """Create Crossings Cost Raster"""
    try:
        crossing_layer = QgsProject.instance().mapLayer(dialog.crossingComboBox.currentData())
        ref_layer = QgsProject.instance().mapLayer(dialog.crossingRefRasterComboBox.currentData())
        output_path = dialog.crossingOutputPath.text().strip()
        crossing_cost = float(dialog.crossingCostInput.text())
        no_crossing_cost = float(dialog.crossingNoCostInput.text())

        if not all([crossing_layer, ref_layer, output_path]):
            raise ValueError("All inputs must be specified.")

        dialog.log_message("Creating Crossings Costs Raster...", "Crossings")
        params = {
            'INPUT': crossing_layer,
            'INPUT_RASTER': ref_layer,
            'BURN_VALUE': crossing_cost,
            'NODATA_VALUE': no_crossing_cost,
            'OUTPUT': output_path
        }
        result = processing.run("gdal:rasterize", params)
        
        if result and 'OUTPUT' in result:
            new_layer = QgsRasterLayer(output_path, "Crossings Costs")
            if new_layer.isValid():
                QgsProject.instance().addMapLayer(new_layer)
                dialog.log_message(f"Crossings Costs Raster created successfully at: {output_path}", "Crossings")
            else:
                dialog.log_message("Failed to load created crossings costs layer.", "Crossings")
        else:
            raise RuntimeError("Rasterization failed to return the expected output.")

    except Exception as e:
        dialog.log_message(f"Creating Crossings Costs Raster Failed: {str(e)}", "Crossings") 