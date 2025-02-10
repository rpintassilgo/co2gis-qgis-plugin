from typing import TYPE_CHECKING
from PyQt5.QtWidgets import (
    QVBoxLayout, QLabel, QComboBox, QTableWidget, QLineEdit, QPushButton,
    QFormLayout, QHeaderView, QTextEdit, QTabWidget, QGroupBox, QHBoxLayout, QFileDialog, QDialog
)
from qgis.core import QgsProject
from .ui import setup_ui
from .dropdowns import populate_layer_step_by_step_dropdowns
from .run_steps import run_step, run_step1_logic, run_step2_logic, run_step3_logic, run_step4_logic, run_step5_logic, run_step_resample
from ..complete_dialog import populate_land_use_classes_table

if TYPE_CHECKING:
    from . import StepByStepDialog

class StepByStepDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Explicitly declare attributes for widgets
        self.pointsComboBox: QComboBox
        self.demComboBox: QComboBox
        self.slopeRasterPath: QLineEdit
        self.slopeRasterBrowse: QPushButton
        self.create_slope_button: QPushButton
        self.terrainComboBox: QComboBox
        self.classify_button: QPushButton
        self.classTable: QTableWidget
        self.costsRasterPath: QLineEdit
        self.costsRasterBrowse: QPushButton
        self.create_land_use_costs_button: QPushButton
        self.step3LandUseDropdown: QComboBox
        self.step3SlopeDropdown: QComboBox
        self.landUseCostWeightInput: QLineEdit
        self.slopeRasterWeightInput: QLineEdit
        self.combinedRasterPath: QLineEdit
        self.combinedRasterBrowse: QPushButton
        self.combine_button: QPushButton
        self.step4Dropdown: QComboBox
        self.clippedRasterPath: QLineEdit
        self.clippedRasterBrowse: QPushButton
        self.clip_button: QPushButton
        self.step5Dropdown: QComboBox
        self.finalPath: QLineEdit
        self.finalBrowse: QPushButton
        self.final_button: QPushButton
        self.resampleRasterComboBox: QComboBox
        self.originalResolutionInput: QLineEdit
        self.targetResolutionInput: QLineEdit
        self.resamplingMethodComboBox: QComboBox
        self.resampleOutputPath: QLineEdit
        self.resampleBrowse: QPushButton
        self.runResampleButton: QPushButton
        self.log_output: QTextEdit
        self.clear_log_button: QPushButton

        # Setup UI and populate dropdowns
        setup_ui(self)
        populate_layer_step_by_step_dropdowns(self)
        QgsProject.instance().layersAdded.connect(lambda: populate_layer_step_by_step_dropdowns(self))

        # Connect buttons to step execution functions
        self.classify_button.clicked.connect(lambda: populate_land_use_classes_table(self))
        self.create_slope_button.clicked.connect(lambda: run_step(self, 2, run_step2_logic))
        self.create_land_use_costs_button.clicked.connect(lambda: run_step(self, 1, run_step1_logic))
        self.combine_button.clicked.connect(lambda: run_step(self, 3, run_step3_logic))
        self.clip_button.clicked.connect(lambda: run_step(self, 4, run_step4_logic))
        self.final_button.clicked.connect(lambda: run_step(self, 5, run_step5_logic))
        self.runResampleButton.clicked.connect(lambda: run_step(self, 6, run_step_resample)) 
        self.clear_log_button.clicked.connect(self.clear_logs)

    def log_message(self, message: str):
        """Append a message to the log output."""
        self.log_output.append(message)
        
    def clear_logs(self):
        self.log_output.clear()

def open_step_by_step_dialog(parent):
    """Opens the Step-by-Step Analysis dialog."""
    step_dialog = StepByStepDialog(parent)
    step_dialog.exec_()
