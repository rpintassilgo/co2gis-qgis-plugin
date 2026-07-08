from typing import Optional

from qgis.core import QgsProject
from qgis.gui import QgsFieldComboBox
from qgis.PyQt import sip
from qgis.PyQt.QtCore import Q_ARG, QMetaObject, Qt
from qgis.PyQt.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QTableWidget,
    QTextEdit,
    QWidget,
)

from .ui.settings_dialog import load_network_mode_experimental, load_rcost_memory_mb
from .ui.tabs.aux_tab import connect_aux_signals
from .ui.tabs.corridors_tab import connect_corridors_signals
from .ui.tabs.crossings_tab import connect_crossings_signals
from .ui.tabs.land_use_tab import connect_land_use_signals
from .ui.tabs.lcp_tab import connect_lcp_signals
from .ui.tabs.price_estimation_tab import connect_price_estimation_signals
from .ui.tabs.slope_tab import connect_slope_signals
from .ui_manager import setup_ui
from .utils import populate_layer_dropdowns, update_pipeline_length, update_resolution_field


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

        # LCP tab — Single/Network routing (Network experimental; built always, mode selector shown
        # only when the toggle is on). The combined-raster picker (lcpInputDropdown) is shared.
        self.lcpModeSingleRadio: QRadioButton
        self.lcpModeNetworkRadio: QRadioButton
        self.lcpModeButtonGroup: QButtonGroup
        self._routingModeRow: QWidget
        self._routingStack: QStackedWidget
        self.networkMethodHeuristicRadio: QRadioButton
        self.networkMethodMilpRadio: QRadioButton
        self.networkMethodButtonGroup: QButtonGroup
        self.networkSourcesDropdown: QComboBox
        self.networkSinksDropdown: QComboBox
        self.networkFlowField: QgsFieldComboBox
        self.networkCapacityField: QgsFieldComboBox
        self.networkCaptureTargetInput: QLineEdit
        self._networkCaptureRow: QWidget
        self.networkOutputFolder: QLineEdit
        self.networkOutputBrowse: QPushButton
        self.network_button: QPushButton

        # Price Estimation — Single/Network mode (Network experimental; the network vector carries a
        # per-segment flow so each segment is sized for its own diameter). Single picker is shared.
        self.priceModeSingleRadio: QRadioButton
        self.priceModeNetworkRadio: QRadioButton
        self.priceModeButtonGroup: QButtonGroup
        self._priceModeRow: QWidget
        self._priceVectorStack: QStackedWidget
        self._priceFlowInputStack: QStackedWidget
        self.priceNetworkVectorDropdown: QComboBox
        self.priceNetworkFlowField: QgsFieldComboBox

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
        self.boosterVariableCostInput: QLineEdit
        self.boosterFixedCostInput: QLineEdit
        self.boosterEfficiencyInput: QLineEdit
        self.calculatePriceButton: QPushButton
        self.show_formulas_button: QPushButton
        self.calcModePreciseRadio: QRadioButton
        self.calcModeFastRadio: QRadioButton
        self.calcModeButtonGroup: QButtonGroup

        self.settings_button: QPushButton
        self.log_output: QTextEdit
        self.clear_log_button: QPushButton

        self._is_updating_weights = False

        # Global settings (persisted via QgsSettings, editable from the header Settings dialog)
        self.rcost_memory_mb = load_rcost_memory_mb()
        self.network_mode_experimental = load_network_mode_experimental()

        # Setup UI
        setup_ui(self)

        # Make all dropdowns searchable
        self._make_all_dropdowns_searchable()

        # Populate dropdowns, and keep them in sync as layers are added.
        # Connect a bound method (not a lambda) so it can be disconnected in cleanup().
        populate_layer_dropdowns(self)
        QgsProject.instance().layersAdded.connect(self._on_layers_added)

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
        from .utils import DROPDOWN_REGISTRY, make_searchable_dropdown

        for attr, _kind, _warning in DROPDOWN_REGISTRY:
            make_searchable_dropdown(getattr(self, attr))

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

    def _on_layers_added(self):
        """Slot for QgsProject.layersAdded — refresh the layer dropdowns."""
        populate_layer_dropdowns(self)

    def cleanup(self):
        """Disconnect global signals before the dialog is disposed (plugin unload)."""
        try:
            QgsProject.instance().layersAdded.disconnect(self._on_layers_added)
        except (TypeError, RuntimeError):
            pass  # already disconnected / nothing connected

    def _log_output_alive(self) -> bool:
        """True only if the log widget exists and its C++ object is not deleted.

        ``hasattr`` alone is not enough: after the dialog is disposed on plugin unload the
        Python attribute survives while the underlying QTextEdit is gone, so invoking a method on
        it raises ``RuntimeError``. ``sip.isdeleted`` is the reliable guard.
        """
        return hasattr(self, "log_output") and not sip.isdeleted(self.log_output)

    def log_message(self, message: str, tab_name: Optional[str] = None):
        """Thread-safe method to append a message to the log output."""
        if self._log_output_alive():
            formatted_message = f"[{tab_name}] {message}" if tab_name else message
            QMetaObject.invokeMethod(
                self.log_output, "append", Qt.ConnectionType.QueuedConnection, Q_ARG(str, formatted_message)
            )

    def clear_logs(self):
        """Clear the log output."""
        if self._log_output_alive():
            QMetaObject.invokeMethod(self.log_output, "clear", Qt.ConnectionType.QueuedConnection)
