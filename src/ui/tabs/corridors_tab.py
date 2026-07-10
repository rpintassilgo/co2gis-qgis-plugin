from typing import TYPE_CHECKING

from qgis.core import QgsProject, QgsRasterLayer
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
)

from ...core.factors.corridors import create_corridor_cost_raster_with_buffers
from ...task_manager import run_task
from ...utils import get_layer_path, layer_from_dropdown, load_raster_result
from ...widgets.browse_row import add_output_path_row

if TYPE_CHECKING:
    from ...analysis_dialog import AnalysisDialog


def setup_corridors_tab(dialog: "AnalysisDialog", layout: QFormLayout):
    # Corridor and reference selection
    dialog.corridorComboBox = QComboBox()
    layout.addRow(QLabel("Select Corridor Vector:"), dialog.corridorComboBox)
    dialog.corridorRefRasterComboBox = QComboBox()
    layout.addRow(QLabel("Select Reference Raster:"), dialog.corridorRefRasterComboBox)

    # Corridor buffer distance
    # Note: this can be edited if you want, if you want to consider a wider area for the corridor.
    # For example, if we set it to 100, we're saying 100 meters around the corridor will have that cheaper cost.
    dialog.corridorBufferInput = QLineEdit("25")
    layout.addRow(QLabel("Corridor Buffer Distance (meters):"), dialog.corridorBufferInput)

    # Cost inputs
    dialog.corridorPresentOffshoreInput = QLineEdit("2.7")
    layout.addRow(QLabel("Cost for corridor present offshore:"), dialog.corridorPresentOffshoreInput)
    dialog.corridorPresentOnshoreInput = QLineEdit("0.9")
    layout.addRow(QLabel("Cost for corridor present onshore:"), dialog.corridorPresentOnshoreInput)
    dialog.corridorAbsentOffshoreInput = QLineEdit("3")
    layout.addRow(QLabel("Cost for corridor absent offshore:"), dialog.corridorAbsentOffshoreInput)
    dialog.corridorAbsentOnshoreInput = QLineEdit("1")
    layout.addRow(QLabel("Cost for corridor absent onshore:"), dialog.corridorAbsentOnshoreInput)

    # Land-use selection & water-body table
    dialog.corridorLandUseComboBox = QComboBox()
    layout.addRow(QLabel("Select Land Use Layer:"), dialog.corridorLandUseComboBox)
    dialog.corridorLandUseTable = QTableWidget()
    dialog.corridorLandUseTable.setColumnCount(3)
    dialog.corridorLandUseTable.setHorizontalHeaderLabels(["Class ID", "Class Name", "Water Body"])
    dialog.corridorLandUseTable.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    layout.addRow(dialog.corridorLandUseTable)

    # Output path
    path_layout = add_output_path_row(dialog, "corridorOutputPath", "corridorBrowse", "tif")
    layout.addRow(path_layout)

    # Run button
    dialog.runCreateRasterFromCorridorButton = QPushButton("Create Corridors Costs Raster")
    layout.addRow(dialog.runCreateRasterFromCorridorButton)

    dialog.corridorLandUseComboBox.currentIndexChanged.connect(
        lambda: populate_corridor_land_use_table(dialog, dialog.corridorLandUseComboBox.currentData())
    )


def populate_corridor_land_use_table(dialog, layer_id):
    from qgis.PyQt.QtWidgets import QTableWidgetItem

    dialog.corridorLandUseTable.setRowCount(0)
    lyr = QgsProject.instance().mapLayer(layer_id)
    if not isinstance(lyr, QgsRasterLayer):
        return
    rnd = lyr.renderer()
    if not hasattr(rnd, "classes"):
        return
    for entry in rnd.classes():
        row = dialog.corridorLandUseTable.rowCount()
        dialog.corridorLandUseTable.insertRow(row)
        id_item = QTableWidgetItem(str(entry.value))
        id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        dialog.corridorLandUseTable.setItem(row, 0, id_item)
        name_item = QTableWidgetItem(entry.label)
        name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        dialog.corridorLandUseTable.setItem(row, 1, name_item)
        chk = QCheckBox()
        chk.setStyleSheet("margin-left:50%;margin-right:50%;")
        dialog.corridorLandUseTable.setCellWidget(row, 2, chk)


def connect_corridors_signals(dialog: "AnalysisDialog"):
    dialog.runCreateRasterFromCorridorButton.clicked.connect(
        lambda _: run_task(
            dialog,
            "Create Corridors Costs Raster",
            work=_corridors_work,
            prepare=_corridors_prepare,
            publish=_corridors_publish,
        )
    )


def _corridors_prepare(dialog: "AnalysisDialog") -> dict:
    """Main thread: read widgets, resolve layers to paths, read the water-body table."""
    corridor_layer = layer_from_dropdown(dialog.corridorComboBox)
    ref_layer = layer_from_dropdown(dialog.corridorRefRasterComboBox)
    land_use_layer = layer_from_dropdown(dialog.corridorLandUseComboBox)
    output_path = dialog.corridorOutputPath.text().strip()

    if not all([corridor_layer, ref_layer, land_use_layer, output_path]):
        raise ValueError("Select all inputs and output path.")

    # Parse costs and buffer distance
    present_offshore_cost = float(dialog.corridorPresentOffshoreInput.text())
    present_onshore_cost = float(dialog.corridorPresentOnshoreInput.text())
    absent_offshore_cost = float(dialog.corridorAbsentOffshoreInput.text())
    absent_onshore_cost = float(dialog.corridorAbsentOnshoreInput.text())
    buffer_distance = float(dialog.corridorBufferInput.text())

    # Build water IDs set from the land-use table (widget read — must stay on main thread).
    water_ids = set()
    for r in range(dialog.corridorLandUseTable.rowCount()):
        item = dialog.corridorLandUseTable.item(r, 0)
        chk = dialog.corridorLandUseTable.cellWidget(r, 2)
        if item and chk and chk.isChecked():
            try:
                water_ids.add(float(item.text()))
            except ValueError:
                pass  # Skip invalid entries

    dialog.log_message(f"Water classes: {sorted(water_ids)}", "Corridors")
    if not water_ids:
        raise ValueError("No water body classes selected. Please check at least one water body class.")

    dialog.log_message("Creating corridors cost raster...", "Corridors")

    return {
        "corridor_path": get_layer_path(corridor_layer),
        "land_use_path": get_layer_path(land_use_layer),
        "land_use_crs": land_use_layer.crs().toWkt(),
        "ref_path": get_layer_path(ref_layer),
        "water_ids": water_ids,
        "present_offshore_cost": present_offshore_cost,
        "present_onshore_cost": present_onshore_cost,
        "absent_offshore_cost": absent_offshore_cost,
        "absent_onshore_cost": absent_onshore_cost,
        "buffer_distance": buffer_distance,
        "output_path": output_path,
        "log": lambda msg: dialog.log_message(msg, "Corridors"),
    }


def _corridors_work(params: dict) -> str:
    """Background thread: build the corridor cost raster, return its path."""
    return create_corridor_cost_raster_with_buffers(
        params["corridor_path"],
        params["land_use_path"],
        params["land_use_crs"],
        params["ref_path"],
        params["water_ids"],
        params["present_offshore_cost"],
        params["present_onshore_cost"],
        params["absent_offshore_cost"],
        params["absent_onshore_cost"],
        params["buffer_distance"],
        params["output_path"],
        log=params["log"],
    )


def _corridors_publish(dialog: "AnalysisDialog", output_path: str):
    """Main thread: load the resulting corridor cost raster into the project."""
    load_raster_result(dialog, output_path, "Corridors", f"Corridors cost raster created at: {output_path}")
