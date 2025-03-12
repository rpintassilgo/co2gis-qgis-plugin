from PyQt5.QtWidgets import QDialog
from qgis.core import QgsProject
from .ui import setup_ui
from PyQt5.QtWidgets import (
    QVBoxLayout, QLabel, QComboBox, QTableWidget, QLineEdit, QPushButton,
    QFormLayout, QHeaderView, QTextEdit, QTabWidget, QGroupBox, QHBoxLayout
)
from .dropdowns import populate_layer_costs_dropdowns

class PipelineCostsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Declare attributes for UI elements
        self.pipelineVectorDropdown: QComboBox
        self.landUseCostsDropdown: QComboBox
        self.slopeCostsDropdown: QComboBox
        self.standardizedCostInput: QLineEdit
        self.frictionFactorInput: QLineEdit
        self.massFlowRateInput: QLineEdit
        self.co2DensityInput: QLineEdit
        self.pressureDropInput: QLineEdit
        self.log_output: QTextEdit
        self.tabs: QTabWidget
        self.clear_log_button: QPushButton

        setup_ui(self)

        # Connect button signals
        #self.calculateButton.clicked.connect(self.calculate_pipeline_costs)
        #self.clearLogButton.clicked.connect(self.clear_logs)
        populate_layer_costs_dropdowns(self)
        

    def calculate_pipeline_costs(self):
        """Placeholder function to calculate costs."""
        self.log_message("Pipeline costs calculation started...")

    def log_message(self, message: str):
        """Append a message to the log output."""
        self.log_output.append(message)

    def clear_logs(self):
        """Clear log output."""
        self.log_output.clear()
