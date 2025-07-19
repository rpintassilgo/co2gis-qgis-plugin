from typing import TYPE_CHECKING
from PyQt5.QtWidgets import (
    QLabel, QComboBox, QLineEdit, QPushButton, QHBoxLayout, QFormLayout
)
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
        lambda checked: run_in_background(dialog, run_crossings_cost_creation)
    )

def run_crossings_cost_creation(dialog: 'AnalysisDialog'):
    """Create a single-band cost raster from a vector, aligned to a reference raster"""
    try:
        # Get selected layers and parameters
        crossing_layer = QgsProject.instance().mapLayer(dialog.crossingComboBox.currentData())
        ref_layer = QgsProject.instance().mapLayer(dialog.crossingRefRasterComboBox.currentData())
        output_path = dialog.crossingOutputPath.text().strip()
        crossing_cost = float(dialog.crossingCostInput.text())
        no_crossing_cost = float(dialog.crossingNoCostInput.text())

        if not crossing_layer or not ref_layer or not output_path:
            raise ValueError("Please specify vector, reference raster and output path.")

        dialog.log_message("Creating Crossings Costs Raster...", "Crossings")

        # Rasterize: initialize all cells with no_crossing_cost, then burn crossing_cost where features exist
        params = {
            'INPUT': crossing_layer,
            'FIELD': None,
            'BURN': crossing_cost,
            'USE_Z': False,
            'UNITS': 0,             # Pixel units for width/height
            'WIDTH': ref_layer.width(),
            'HEIGHT': ref_layer.height(),
            'EXTENT': ref_layer.extent(),
            'INIT': no_crossing_cost,
            'DATA_TYPE': 5,         # Float32 for single band
            'EXTRA': '',            # Extra GDAL flags if needed
            'OUTPUT': output_path
        }
        # Use GDAL rasterize for explicit single-band control
        result = processing.run('gdal:rasterize', params)
        
        # Validate and load
        if not result or 'OUTPUT' not in result:
            raise RuntimeError("Rasterization failed to return output.")
            
        output_raster = result['OUTPUT']
        if not output_raster:
            raise RuntimeError("Rasterization returned no output.")

        new_layer = QgsRasterLayer(output_raster, "Crossings Cost")
        if not new_layer.isValid():
            raise RuntimeError("Failed to load the resulting raster layer.")

        QgsProject.instance().addMapLayer(new_layer)
        dialog.log_message(f"Raster created at {output_path}", "Crossings")

    except Exception as e:
        dialog.log_message(f"Crossings raster creation failed: {e}", "Crossings")
