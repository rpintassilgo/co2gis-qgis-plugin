from typing import TYPE_CHECKING
from PyQt5.QtWidgets import (
    QVBoxLayout, QLabel, QComboBox, QTableWidget, QLineEdit, QPushButton, QCheckBox, QTableWidgetItem,
    QFormLayout, QHeaderView, QTextEdit, QTabWidget, QGroupBox, QHBoxLayout, QFileDialog, QDialog, QSpinBox
)
from PyQt5.QtCore import Qt
from qgis.core import QgsProject, QgsApplication
from .ui import setup_ui, update_resolution_field, update_pipeline_length, FormulaDialog
from .dropdowns import populate_layer_step_by_step_dropdowns
from .run_steps import (
    run_step, run_step1_logic, run_step2_logic, run_step3_logic, 
    run_step4_logic, run_step5_logic, run_step7_logic, run_step8_logic, 
    run_step_resample, run_price_estimation_logic, run_slope_costs_logic
)
from .land_use import populate_land_use_classes_table

if TYPE_CHECKING:
    from . import StepByStepDialog

class StepByStepDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Explicitly declare attributes for widgets
        self.pointsComboBox: QComboBox
        self.clipPointVectorComboBox: QComboBox
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
        self.step3CorridorsDropdown: QComboBox
        self.step3CrossingsDropdown: QComboBox
        self.weight_sliders: list
        self.weight_spinboxes: list
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
        self.vectorComboBox: QComboBox
        self.vector2ComboBox: QComboBox
        self.resampleOutputPath: QLineEdit
        self.resampleBrowse: QPushButton
        self.runResampleButton: QPushButton
        self.log_output: QTextEdit
        self.clear_log_button: QPushButton
        self.slopeCostTable: QTableWidget
        self.addSlopeRowButton: QPushButton
        self.removeSlopeRowButton: QPushButton
        self.slopeLayerComboBox: QComboBox
        self.slopeCostsRasterPath: QLineEdit
        self.slopeCostsRasterBrowse: QPushButton

        # Price Estimation widgets
        self.pipelineVectorDropdown: QComboBox
        self.landUseCostsDropdown: QComboBox
        self.slopeCostsDropdown: QComboBox
        self.corridorsCostsDropdown: QComboBox
        self.crossingsCostsDropdown: QComboBox
        self.landUseCostsResInput: QLineEdit
        self.slopeCostsResInput: QLineEdit
        self.corridorsCostsResInput: QLineEdit
        self.crossingsCostsResInput: QLineEdit
        self.pipelineLengthInput: QLineEdit
        self.numInfrastructureInput: QLineEdit
        self.standardizedCostFactorInput: QLineEdit
        self.frictionFactorInput: QLineEdit
        self.co2MassFlowRateInput: QLineEdit
        self.co2densityInput: QLineEdit
        self.pressureDropInput: QLineEdit
        self.calculatePriceButton: QPushButton
        self.show_formulas_button: QPushButton

        self.land_use_populating_task = None

        # Setup UI and populate dropdowns
        setup_ui(self)
        populate_layer_step_by_step_dropdowns(self)
        QgsProject.instance().layersAdded.connect(lambda: populate_layer_step_by_step_dropdowns(self))
        setup_slope_cost_table_logic(self)

        # Manually trigger updates for Price Estimation tab after population
        update_pipeline_length(self)
        update_resolution_field(self, self.landUseCostsDropdown, self.landUseCostsResInput)
        update_resolution_field(self, self.slopeCostsDropdown, self.slopeCostsResInput)
        update_resolution_field(self, self.corridorsCostsDropdown, self.corridorsCostsResInput)
        update_resolution_field(self, self.crossingsCostsDropdown, self.crossingsCostsResInput)

        # Connect buttons to step execution functions
        self.terrainComboBox.currentIndexChanged.connect(lambda: populate_land_use_classes_table(self))
        self.create_slope_button.clicked.connect(lambda: run_step(self, 2, run_step2_logic))
        self.create_slope_costs_button.clicked.connect(lambda: run_step(self, 9, run_slope_costs_logic))
        self.create_land_use_costs_button.clicked.connect(lambda: run_step(self, 1, run_step1_logic))
        self.combine_button.clicked.connect(lambda: run_step(self, 3, run_step3_logic))
        self.clip_button.clicked.connect(lambda: run_step(self, 4, run_step4_logic))
        self.final_button.clicked.connect(lambda: run_step(self, 5, run_step5_logic))
        self.runResampleButton.clicked.connect(lambda: run_step(self, 6, run_step_resample)) 
        self.clear_log_button.clicked.connect(self.clear_logs)
        self.runCombineVectorsButton.clicked.connect(lambda: run_step(self, 8, run_step8_logic))
        self.runCreateRasterFromVectorButton.clicked.connect(lambda: run_step(self, 7, run_step7_logic))
        self.calculatePriceButton.clicked.connect(lambda: run_step(self, 10, run_price_estimation_logic))
        self.show_formulas_button.clicked.connect(self.open_formulas_dialog)

        # Connections for Price Estimation tab
        self.pipelineVectorDropdown.currentIndexChanged.connect(lambda: update_pipeline_length(self))
        self.landUseCostsDropdown.currentIndexChanged.connect(
            lambda: update_resolution_field(self, self.landUseCostsDropdown, self.landUseCostsResInput)
        )
        self.slopeCostsDropdown.currentIndexChanged.connect(
            lambda: update_resolution_field(self, self.slopeCostsDropdown, self.slopeCostsResInput)
        )
        self.corridorsCostsDropdown.currentIndexChanged.connect(
            lambda: update_resolution_field(self, self.corridorsCostsDropdown, self.corridorsCostsResInput)
        )
        self.crossingsCostsDropdown.currentIndexChanged.connect(
            lambda: update_resolution_field(self, self.crossingsCostsDropdown, self.crossingsCostsResInput)
        )

    def open_formulas_dialog(self):
        """Opens the dialog that displays the formulas."""
        dialog = FormulaDialog(self)
        dialog.exec_()

    def log_message(self, message: str):
        """Append a message to the log output."""
        self.log_output.append(message)
        
    def clear_logs(self):
        self.log_output.clear()
        
    def get_slope_cost_intervals(self):
        """Extract slope intervals and costs from the table."""
        intervals = []
        for row in range(self.slopeCostTable.rowCount()):
            min_spin = self.slopeCostTable.cellWidget(row, 0)
            max_spin = self.slopeCostTable.cellWidget(row, 1)
            cost_item = self.slopeCostTable.item(row, 2)
            no_limit_checkbox = self.slopeCostTable.cellWidget(row, 3)

            min_val = min_spin.value()
            max_val = max_spin.value() if not no_limit_checkbox.isChecked() else None
            cost = float(cost_item.text())

            intervals.append({"min": min_val, "max": max_val, "cost": cost})

        return intervals

    def get_land_use_costs(self):
        """Extracts land use class costs from the table."""
        costs = {}
        for row in range(self.classTable.rowCount()):
            class_id = int(self.classTable.item(row, 0).text())
            cost = float(self.classTable.item(row, 2).text())
            costs[class_id] = cost
        return costs

def open_step_by_step_dialog(parent):
    """Opens the Step-by-Step Analysis dialog."""
    step_dialog = StepByStepDialog(parent)
    step_dialog.exec_()
    
def setup_slope_cost_table_logic(self):
    """Connects buttons to their functions for the slope cost table."""
    self.addSlopeRowButton.clicked.connect(lambda: add_slope_row(self))
    self.removeSlopeRowButton.clicked.connect(lambda: remove_selected_slope_row(self))
    add_slope_row(self)  # Add initial row

def add_slope_row(self):
    """Add a new row to the slope cost table."""
    row_position = self.slopeCostTable.rowCount()
    self.slopeCostTable.insertRow(row_position)

    # Min % Slope SpinBox
    min_spin = QSpinBox()
    min_spin.setRange(0, 1000)
    self.slopeCostTable.setCellWidget(row_position, 0, min_spin)

    # Max % Slope SpinBox
    max_spin = QSpinBox()
    max_spin.setRange(0, 1000)
    self.slopeCostTable.setCellWidget(row_position, 1, max_spin)

    # Cost Input
    cost_item = QTableWidgetItem("1.0")
    self.slopeCostTable.setItem(row_position, 2, cost_item)

    # No Upper Limit Checkbox
    no_limit_checkbox = QCheckBox()
    self.slopeCostTable.setCellWidget(row_position, 3, no_limit_checkbox)

    # Connect checkbox logic to disable Max % Slope
    def toggle_max_spin(state):
        max_spin.setDisabled(state == Qt.Checked)
        if state == Qt.Checked:
            max_spin.setValue(0)

    no_limit_checkbox.stateChanged.connect(toggle_max_spin)

def remove_selected_slope_row(self):
    """Remove selected rows from the slope cost table."""
    selected_rows = set(idx.row() for idx in self.slopeCostTable.selectedIndexes())
    for row in sorted(selected_rows, reverse=True):
        self.slopeCostTable.removeRow(row)

