import os
from typing import TYPE_CHECKING

from qgis.core import QgsProject, QgsRasterLayer
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
)

from ...constants.slope import COMET_SLOPE_INTERVALS
from ...core.factors.slope import create_slope_costs_from_slope, create_slope_layer_from_dem
from ...task_manager import run_task
from ...utils import get_layer_path, layer_from_dropdown
from ...widgets.browse_row import add_output_path_row, make_group_box

if TYPE_CHECKING:
    from ...analysis_dialog import AnalysisDialog


def setup_slope_tab(dialog: "AnalysisDialog", layout: QFormLayout):
    """Sets up the Slope tab."""
    createSlopeLayout = QFormLayout()

    dialog.demComboBox = QComboBox()
    createSlopeLayout.addRow(QLabel("Select DEM Layer:"), dialog.demComboBox)

    slopeFileLayout = add_output_path_row(
        dialog, "slopeRasterPath", "slopeRasterBrowse", "tif", "Choose output path for Slope Raster"
    )
    createSlopeLayout.addRow(slopeFileLayout)

    dialog.create_slope_button = QPushButton("Create Slope Raster from DEM")
    createSlopeLayout.addRow(dialog.create_slope_button)

    layout.addRow(make_group_box("Create Slope from DEM", createSlopeLayout))

    slopeCostsLayout = QFormLayout()

    dialog.slopeLayerComboBox = QComboBox()
    slopeCostsLayout.addRow(QLabel("Select Slope Layer:"), dialog.slopeLayerComboBox)

    slopeCostsLayout.addRow(QLabel("Define Slope Cost Intervals:"))

    dialog.slopeCostTable = QTableWidget()
    dialog.slopeCostTable.setColumnCount(4)
    dialog.slopeCostTable.setHorizontalHeaderLabels(["Min % Slope", "Max % Slope", "Cost", "No Upper Limit"])
    dialog.slopeCostTable.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    slopeCostsLayout.addRow(dialog.slopeCostTable)

    slopeTableButtonsLayout = QHBoxLayout()
    dialog.addSlopeRowButton = QPushButton("Add Row")
    dialog.removeSlopeRowButton = QPushButton("Remove Selected Row")
    dialog.slopePopulateCometButton = QPushButton("Populate according to COMET")
    slopeTableButtonsLayout.addWidget(dialog.addSlopeRowButton)
    slopeTableButtonsLayout.addWidget(dialog.removeSlopeRowButton)
    slopeTableButtonsLayout.addWidget(dialog.slopePopulateCometButton)
    slopeCostsLayout.addRow(slopeTableButtonsLayout)

    slopeCostsFileLayout = add_output_path_row(
        dialog, "slopeCostsRasterPath", "slopeCostsRasterBrowse", "tif", "Choose output path for Slope Costs Raster"
    )
    slopeCostsLayout.addRow(slopeCostsFileLayout)

    dialog.create_slope_costs_button = QPushButton("Create Slope Costs Raster")
    slopeCostsLayout.addRow(dialog.create_slope_costs_button)

    layout.addRow(make_group_box("Create Slope Costs", slopeCostsLayout))

    setup_slope_cost_table_logic(dialog)


def connect_slope_signals(dialog: "AnalysisDialog"):
    """Connects signals for the Slope tab."""
    dialog.create_slope_button.clicked.connect(
        lambda checked: run_task(
            dialog, "Create Slope Raster", work=_slope_work, prepare=_slope_prepare, publish=_slope_publish
        )
    )
    dialog.create_slope_costs_button.clicked.connect(
        lambda checked: run_task(
            dialog,
            "Create Slope Costs Raster",
            work=_slope_costs_work,
            prepare=_slope_costs_prepare,
            publish=_slope_costs_publish,
        )
    )


# ── Create slope raster from DEM ──────────────────────────────────────────────


def _slope_prepare(dialog: "AnalysisDialog") -> dict:
    """Main thread: read DEM layer + output path, resolve to a source path."""
    dem_layer = layer_from_dropdown(dialog.demComboBox)
    output_path = dialog.slopeRasterPath.text()

    if not dem_layer:
        raise ValueError("No DEM layer selected.")
    if not output_path:
        raise ValueError("No output path specified for Slope Raster.")

    dialog.log_message("Creating Slope Raster from DEM...", "Slope")
    return {
        "dem_path": get_layer_path(dem_layer),
        "output_path": output_path,
        "log": lambda msg: dialog.log_message(msg, "Slope"),
    }


def _slope_work(params: dict) -> str:
    """Background thread: run the qgis:slope algorithm, write the raster."""
    return create_slope_layer_from_dem(params["dem_path"], params["output_path"], log=params["log"])


def _slope_publish(dialog: "AnalysisDialog", output_path: str):
    """Main thread: load the slope raster into the project."""
    layer_name = os.path.splitext(os.path.basename(output_path))[0]
    slope_layer = QgsRasterLayer(output_path, layer_name)
    if not slope_layer.isValid():
        raise RuntimeError("Failed to load created slope layer.")
    QgsProject.instance().addMapLayer(slope_layer)
    dialog.log_message(f"Slope Raster created at: {output_path}", "Slope")


# ── Create slope costs raster ─────────────────────────────────────────────────


def _slope_costs_prepare(dialog: "AnalysisDialog") -> dict:
    """Main thread: read intervals (table) + slope layer + output path."""
    intervals = get_slope_cost_intervals(dialog)
    slope_layer = layer_from_dropdown(dialog.slopeLayerComboBox)
    output_path = dialog.slopeCostsRasterPath.text()

    if not slope_layer:
        raise ValueError("No slope layer selected.")
    if not output_path:
        raise ValueError("No output path specified for Slope Costs Raster.")
    if not intervals:
        raise ValueError("No slope cost intervals defined.")

    dialog.log_message("Creating Slope Costs Raster...", "Slope")
    return {
        "slope_path": get_layer_path(slope_layer),
        "intervals": intervals,
        "output_path": output_path,
        "log": lambda msg: dialog.log_message(msg, "Slope"),
    }


def _slope_costs_work(params: dict) -> str:
    """Background thread: apply the cost intervals, write the raster."""
    return create_slope_costs_from_slope(
        params["slope_path"], params["intervals"], params["output_path"], log=params["log"]
    )


def _slope_costs_publish(dialog: "AnalysisDialog", output_path: str):
    """Main thread: load the slope costs raster into the project."""
    layer_name = os.path.splitext(os.path.basename(output_path))[0]
    new_layer = QgsRasterLayer(output_path, layer_name)
    if not new_layer.isValid():
        raise RuntimeError("Failed to load the created Slope Costs raster.")
    QgsProject.instance().addMapLayer(new_layer)
    dialog.log_message(f"Slope Costs Raster created successfully at: {output_path}", "Slope")


def get_slope_cost_intervals(dialog: "AnalysisDialog"):
    """Extract slope intervals and costs from the table."""
    intervals = []
    for row in range(dialog.slopeCostTable.rowCount()):
        min_spin = dialog.slopeCostTable.cellWidget(row, 0)
        max_spin = dialog.slopeCostTable.cellWidget(row, 1)
        cost_item = dialog.slopeCostTable.item(row, 2)
        no_limit_checkbox = dialog.slopeCostTable.cellWidget(row, 3)

        min_val = min_spin.value()
        max_val = max_spin.value() if not no_limit_checkbox.isChecked() else None

        cost_text = cost_item.text() if cost_item else "1.0"
        try:
            cost = float(cost_text)
        except (ValueError, TypeError):
            cost = 1.0  # Default value if parsing fails
            dialog.log_message(f"Invalid cost value '{cost_text}' in row {row + 1}. Using default 1.0.", "Slope")

        intervals.append({"min": min_val, "max": max_val, "cost": cost})

    return intervals


def setup_slope_cost_table_logic(dialog: "AnalysisDialog"):
    """Connects buttons to their functions for the slope cost table."""
    dialog.addSlopeRowButton.clicked.connect(lambda: add_slope_row(dialog))
    dialog.removeSlopeRowButton.clicked.connect(lambda: remove_selected_slope_row(dialog))
    dialog.slopePopulateCometButton.clicked.connect(lambda: populate_slope_table_with_comet_defaults(dialog))

    add_slope_row(dialog)  # Add a single empty row to start


def populate_slope_table_with_comet_defaults(dialog: "AnalysisDialog"):
    """Clear the table and populate with COMET project default slope costs."""
    dialog.slopeCostTable.setRowCount(0)

    for min_val, max_val, cost, no_limit in COMET_SLOPE_INTERVALS:
        add_slope_row(dialog, min_val, max_val, cost, no_limit)


def add_slope_row(dialog: "AnalysisDialog", min_val=None, max_val=None, cost_val=None, no_limit=False):
    """Add a new row to the slope cost table."""
    row_position = dialog.slopeCostTable.rowCount()
    dialog.slopeCostTable.insertRow(row_position)

    min_spin = QSpinBox()
    min_spin.setRange(0, 1000)
    if min_val is not None:
        min_spin.setValue(min_val)
    dialog.slopeCostTable.setCellWidget(row_position, 0, min_spin)

    max_spin = QSpinBox()
    max_spin.setRange(0, 1000)
    if max_val is not None:
        max_spin.setValue(max_val)
    dialog.slopeCostTable.setCellWidget(row_position, 1, max_spin)

    cost_item = QTableWidgetItem(str(cost_val) if cost_val is not None else "1.0")
    dialog.slopeCostTable.setItem(row_position, 2, cost_item)

    no_limit_checkbox = QCheckBox()
    no_limit_checkbox.setChecked(no_limit)
    dialog.slopeCostTable.setCellWidget(row_position, 3, no_limit_checkbox)

    def toggle_max_spin(state):
        is_disabled = state == Qt.CheckState.Checked
        max_spin.setDisabled(is_disabled)
        if is_disabled:
            max_spin.setValue(0)

    no_limit_checkbox.stateChanged.connect(toggle_max_spin)
    toggle_max_spin(Qt.CheckState.Checked if no_limit else Qt.CheckState.Unchecked)


def remove_selected_slope_row(dialog: "AnalysisDialog"):
    """Remove selected rows from the slope cost table."""
    selected_rows = set(idx.row() for idx in dialog.slopeCostTable.selectedIndexes())
    for row in sorted(selected_rows, reverse=True):
        dialog.slopeCostTable.removeRow(row)
