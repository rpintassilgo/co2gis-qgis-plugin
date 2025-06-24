from typing import TYPE_CHECKING
from PyQt5.QtWidgets import (
    QLabel, QComboBox, QLineEdit, QPushButton, QHBoxLayout, QFormLayout
)
from PyQt5.QtCore import Qt
from qgis.core import QgsProject, QgsRasterLayer
from ..task_manager import run_analysis
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