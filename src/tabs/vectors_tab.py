from typing import TYPE_CHECKING
from PyQt5.QtWidgets import (
    QLabel, QComboBox, QLineEdit, QPushButton, QHBoxLayout, QFormLayout
)
from qgis.core import QgsProject, QgsRasterLayer
import processing

from ..task_manager import run_analysis
from ..utils import select_output_file

if TYPE_CHECKING:
    from ..analysis_dialog import AnalysisDialog

def setup_vectors_tab(dialog: 'AnalysisDialog', layout: QFormLayout):
    """Sets up the Vectors (Corridors and Crossings) tab."""
    dialog.vectorRasterComboBox = QComboBox()
    layout.addRow(QLabel("Select Vector:"), dialog.vectorRasterComboBox)
    
    dialog.refRasterComboBox = QComboBox()
    layout.addRow(QLabel("Select Reference Raster:"), dialog.refRasterComboBox)
    
    dialog.hasVectorCostInput = QLineEdit()
    dialog.hasVectorCostInput.setPlaceholderText("Enter cost where vector is present")
    dialog.hasVectorCostInput.setText("3")
    dialog.hasNotVectorCostInput = QLineEdit()
    dialog.hasNotVectorCostInput.setPlaceholderText("Enter cost where vector is absent")
    dialog.hasNotVectorCostInput.setText("1")
    layout.addRow(QLabel("Cost for vector-covered cells:"), dialog.hasVectorCostInput)
    layout.addRow(QLabel("Cost for non-vector cells:"), dialog.hasNotVectorCostInput)
    
    dialog.vectorRasterOutputPath = QLineEdit()
    dialog.vectorRasterOutputPath.setPlaceholderText("Choose output path for Raster")
    dialog.vectorRasterBrowse = QPushButton("Browse")
    dialog.vectorRasterBrowse.clicked.connect(lambda: select_output_file(dialog.vectorRasterOutputPath, "tif"))
    
    outputVectorRasterLayout = QHBoxLayout()
    outputVectorRasterLayout.addWidget(dialog.vectorRasterOutputPath)
    outputVectorRasterLayout.addWidget(dialog.vectorRasterBrowse)
    layout.addRow(outputVectorRasterLayout)
    
    dialog.runCreateRasterFromVectorButton = QPushButton("Create cost raster from vector")
    layout.addRow(dialog.runCreateRasterFromVectorButton)

def connect_vectors_signals(dialog: 'AnalysisDialog'):
    """Connects signals for the Vectors tab."""
    dialog.runCreateRasterFromVectorButton.clicked.connect(lambda: run_analysis(dialog, run_raster_from_vector_creation))

def run_raster_from_vector_creation(dialog: 'AnalysisDialog'):
    """Create Cost Raster from Vector"""
    try:
        vector_layer = QgsProject.instance().mapLayer(dialog.vectorRasterComboBox.currentData())
        output_path = dialog.vectorRasterOutputPath.text().strip()
        cost_with_vector = float(dialog.hasVectorCostInput.text().strip())
        cost_without_vector = float(dialog.hasNotVectorCostInput.text().strip())
        ref_raster = QgsProject.instance().mapLayer(dialog.refRasterComboBox.currentData())

        if not all([vector_layer, output_path, ref_raster]):
            raise ValueError("Missing one or more inputs: vector layer, output path, or reference raster.")

        width = ref_raster.width()
        height = ref_raster.height()
        extent = ref_raster.extent()

        dialog.log_message("Creating cost raster from vector...", "Corridors and Crossings")
        
        rasterized_output = processing.run("gdal:rasterize", {
            'INPUT': vector_layer,
            'FIELD': None,
            'BURN': cost_with_vector,
            'UNITS': 1,
            'WIDTH': width,
            'HEIGHT': height,
            'EXTENT': extent,
            'INIT': cost_without_vector,
            'DATA_TYPE': 5, # Float32
            'OUTPUT': output_path
        })

        if rasterized_output and 'OUTPUT' in rasterized_output:
            dialog.log_message(f"Cost raster created successfully at: {rasterized_output['OUTPUT']}", "Corridors and Crossings")
            new_raster = QgsRasterLayer(rasterized_output['OUTPUT'], "Cost Raster from Vector")
            if new_raster.isValid():
                QgsProject.instance().addMapLayer(new_raster)
            else:
                dialog.log_message("Failed to load the created raster from vector.", "Corridors and Crossings")
    except Exception as e:
        dialog.log_message(f"Raster from Vector creation Failed: {str(e)}", "Corridors and Crossings")
