from PyQt5.QtWidgets import QDialog, QComboBox, QLineEdit, QPushButton, QTableWidget, QTextEdit, QCheckBox
from PyQt5.QtCore import Qt, QMetaObject, Q_ARG
from qgis.core import QgsProject
from typing import Optional

from .ui_manager import setup_ui
from .utils import populate_layer_dropdowns, update_pipeline_length, update_resolution_field
from .tabs.land_use_tab import connect_land_use_signals
from .tabs.slope_tab import connect_slope_signals
from .tabs.aux_tab import connect_aux_signals
from .tabs.lcp_tab import connect_lcp_signals
from .tabs.price_estimation_tab import connect_price_estimation_signals, open_formulas_dialog
from .tabs.crossings_tab import connect_crossings_signals
from .tabs.corridors_tab import connect_corridors_signals

class AnalysisDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Explicitly declare attributes for widgets to aid type hinting and readability
        self.landUseComboBox: QComboBox
        self.landUseCostTable: QTableWidget
        self.showCometValuesButton: QPushButton
        self.populateCometButton: QPushButton
        self.landUseCostsRasterPath: QLineEdit
        self.landUseBrowse: QPushButton
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

        # Crossings tab - Section 1: Crossings Costs
        self.crossingComboBox: QComboBox
        self.crossingRefRasterComboBox: QComboBox
        self.crossingCostInput: QLineEdit
        self.crossingNoCostInput: QLineEdit
        self.crossingOutputPath: QLineEdit
        self.crossingBrowse: QPushButton
        self.runCreateRasterFromCrossingButton: QPushButton
        
        # Crossings tab - Section 2: Number of Crossings (N)
        self.nCrossingVectorComboBox: QComboBox
        self.nCrossingRefRasterComboBox: QComboBox
        self.nCrossingOutputPath: QLineEdit
        self.nCrossingBrowse: QPushButton
        self.runCreateNRasterButton: QPushButton

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
        self.combineNRasterDropdown: QComboBox
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
        self.crossingsVectorDropdown: QComboBox
        self.landUseCostsResInput: QLineEdit
        self.slopeCostsResInput: QLineEdit
        self.corridorsCostsResInput: QLineEdit
        self.crossingsCostsResInput: QLineEdit
        self.pipelineLengthInput: QLineEdit
        self.crossingsVectorDropdown: QComboBox
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
        
        # Make all dropdowns searchable
        self._make_all_dropdowns_searchable()
        
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
    
    def _make_all_dropdowns_searchable(self):
        """Make all layer selection dropdowns searchable with autocomplete."""
        from .utils import make_searchable_dropdown
        
        # Land Use tab
        make_searchable_dropdown(self.landUseComboBox)
        
        # Slope tab
        make_searchable_dropdown(self.demComboBox)
        make_searchable_dropdown(self.slopeLayerComboBox)
        
        # Crossings tab
        make_searchable_dropdown(self.crossingComboBox)
        make_searchable_dropdown(self.crossingRefRasterComboBox)
        make_searchable_dropdown(self.nCrossingVectorComboBox)
        make_searchable_dropdown(self.nCrossingRefRasterComboBox)
        
        # Corridors tab
        make_searchable_dropdown(self.corridorComboBox)
        make_searchable_dropdown(self.corridorRefRasterComboBox)
        
        # Aux tab
        make_searchable_dropdown(self.vectorComboBox)
        make_searchable_dropdown(self.vector2ComboBox)
        make_searchable_dropdown(self.resampleRasterComboBox)
        make_searchable_dropdown(self.clipRasterInputDropdown)
        make_searchable_dropdown(self.clipPointVectorComboBox)
        
        # LCP tab
        make_searchable_dropdown(self.combineLandUseDropdown)
        make_searchable_dropdown(self.combineSlopeDropdown)
        make_searchable_dropdown(self.combineCorridorsDropdown)
        make_searchable_dropdown(self.combineCrossingsDropdown)
        make_searchable_dropdown(self.combineNRasterDropdown)
        make_searchable_dropdown(self.pointsComboBox)
        make_searchable_dropdown(self.lcpInputDropdown)
        
        # Price Estimation tab
        make_searchable_dropdown(self.pipelineVectorDropdown)
        make_searchable_dropdown(self.landUseCostsDropdown)
        make_searchable_dropdown(self.slopeCostsDropdown)
        make_searchable_dropdown(self.corridorsCostsDropdown)
        make_searchable_dropdown(self.crossingsCostsDropdown)
        make_searchable_dropdown(self.crossingsVectorDropdown)

    def connect_signals(self):
        """Connect all signals to their respective slots."""
        connect_land_use_signals(self)
        connect_slope_signals(self)
        connect_aux_signals(self)
        connect_lcp_signals(self)
        connect_price_estimation_signals(self)
        connect_crossings_signals(self)
        connect_corridors_signals(self)
        self.clear_log_button.clicked.connect(self.clear_logs)

    def log_message(self, message: str, tab_name: Optional[str] = None):
        """Thread-safe method to append a message to the log output."""
        if hasattr(self, 'log_output'):
            formatted_message = f"[{tab_name}] {message}" if tab_name else message
            QMetaObject.invokeMethod(
                self.log_output,
                "append",
                Qt.QueuedConnection,
                Q_ARG(str, formatted_message)
            )

    def clear_logs(self):
        """Clear the log output."""
        if hasattr(self, 'log_output'):
            QMetaObject.invokeMethod(
                self.log_output,
                "clear",
                Qt.QueuedConnection
            )

