from PyQt5.QtWidgets import QDialog, QComboBox, QLineEdit, QPushButton, QTableWidget, QTextEdit, QCheckBox
from qgis.core import QgsProject
from typing import Optional

from .ui_manager import setup_ui
from .utils import populate_layer_dropdowns, update_pipeline_length, update_resolution_field
from .tabs.land_use_tab import connect_land_use_signals
from .tabs.slope_tab import connect_slope_signals
from .tabs.vectors_tab import connect_vectors_signals
from .tabs.aux_tab import connect_aux_signals
from .tabs.lcp_tab import connect_lcp_signals
from .tabs.price_estimation_tab import connect_price_estimation_signals, open_formulas_dialog

class AnalysisDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Explicitly declare attributes for widgets to aid type hinting and readability
        self.terrainComboBox: QComboBox
        self.classTable: QTableWidget
        self.costsRasterPath: QLineEdit
        self.costsRasterBrowse: QPushButton
        self.create_land_use_costs_button: QPushButton
        
        self.demComboBox: QComboBox
        self.slopeRasterPath: QLineEdit
        self.slopeRasterBrowse: QPushButton
        self.create_slope_button: QPushButton
        self.slopeLayerComboBox: QComboBox
        self.slopeCostTable: QTableWidget
        self.addSlopeRowButton: QPushButton
        self.removeSlopeRowButton: QPushButton
        self.slopeCostsRasterPath: QLineEdit
        self.slopeCostsRasterBrowse: QPushButton
        self.create_slope_costs_button: QPushButton

        self.vectorRasterComboBox: QComboBox
        self.refRasterComboBox: QComboBox
        self.hasVectorCostInput: QLineEdit
        self.hasNotVectorCostInput: QLineEdit
        self.vectorRasterOutputPath: QLineEdit
        self.vectorRasterBrowse: QPushButton
        self.runCreateRasterFromVectorButton: QPushButton

        self.vectorComboBox: QComboBox
        self.vector2ComboBox: QComboBox
        self.vectorsOutputPath: QLineEdit
        self.vectorsBrowse: QPushButton
        self.runCombineVectorsButton: QPushButton
        self.resampleRasterComboBox: QComboBox
        self.originalResolutionInput: QLineEdit
        self.targetResolutionInput: QLineEdit
        self.resamplingMethodComboBox: QComboBox
        self.resampleOutputPath: QLineEdit
        self.resampleBrowse: QPushButton
        self.runResampleButton: QPushButton
        self.clipPointVectorComboBox: QComboBox
        self.clipRasterInputDropdown: QComboBox
        self.copySymbologyCheckbox: QCheckBox
        self.clippedRasterPath: QLineEdit
        self.clippedRasterBrowse: QPushButton
        self.clip_button: QPushButton

        self.combineLandUseDropdown: QComboBox
        self.combineSlopeDropdown: QComboBox
        self.combineCorridorsDropdown: QComboBox
        self.combineCrossingsDropdown: QComboBox
        self.weight_sliders: list
        self.weight_spinboxes: list
        self.combinedRasterPath: QLineEdit
        self.combinedRasterBrowse: QPushButton
        self.combine_button: QPushButton
        self.pointsComboBox: QComboBox
        self.lcpInputDropdown: QComboBox
        self.costRasterPath: QLineEdit
        self.costRasterBrowse: QPushButton
        self.directionRasterPath: QLineEdit
        self.directionRasterBrowse: QPushButton
        self.drainRasterPath: QLineEdit
        self.drainRasterBrowse: QPushButton
        self.finalPath: QLineEdit
        self.finalBrowse: QPushButton
        self.final_button: QPushButton

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

        self.log_output: QTextEdit
        self.clear_log_button: QPushButton
        
        self._is_updating_weights = False

        # Setup UI
        setup_ui(self)
        
        # Populate dropdowns
        populate_layer_dropdowns(self)
        QgsProject.instance().layersAdded.connect(lambda: populate_layer_dropdowns(self))
        
        # Manually trigger updates for Price Estimation tab after population
        update_pipeline_length(self)
        update_resolution_field(self, self.landUseCostsDropdown, self.landUseCostsResInput)
        update_resolution_field(self, self.slopeCostsDropdown, self.slopeCostsResInput)
        update_resolution_field(self, self.corridorsCostsDropdown, self.corridorsCostsResInput)
        update_resolution_field(self, self.crossingsCostsDropdown, self.crossingsCostsResInput)

        # Connect signals
        self.connect_signals()

    def connect_signals(self):
        """Connect all signals to their respective slots."""
        connect_land_use_signals(self)
        connect_slope_signals(self)
        connect_vectors_signals(self)
        connect_aux_signals(self)
        connect_lcp_signals(self)
        connect_price_estimation_signals(self)
        self.clear_log_button.clicked.connect(self.clear_logs)

    def log_message(self, message: str, tab_name: Optional[str] = None):
        """Append a message to the log output."""
        if tab_name:
            self.log_output.append(f"[{tab_name}] {message}")
        else:
            self.log_output.append(message)
        
    def clear_logs(self):
        """Clear the log output."""
        self.log_output.clear()

