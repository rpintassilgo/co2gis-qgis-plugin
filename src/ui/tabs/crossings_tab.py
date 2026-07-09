import os
from typing import TYPE_CHECKING

from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer
from qgis.PyQt.QtWidgets import QComboBox, QFormLayout, QLabel, QLineEdit, QPushButton

from ...core.factors.crossings import create_crossings_cost_raster, create_n_crossings_raster
from ...task_manager import run_task
from ...utils import get_layer_path, layer_from_dropdown
from ...widgets.browse_row import add_output_path_row, make_group_box

if TYPE_CHECKING:
    from ...analysis_dialog import AnalysisDialog


def setup_crossings_tab(dialog: "AnalysisDialog", layout: QFormLayout):
    """Sets up the Crossings tab with two sections."""

    # ============================================================
    # Section 1: Create Crossings Costs Raster
    # ============================================================
    crossingsCostsLayout = QFormLayout()

    dialog.crossingComboBox = QComboBox()
    crossingsCostsLayout.addRow(QLabel("Select Crossing Vector:"), dialog.crossingComboBox)

    dialog.crossingRefRasterComboBox = QComboBox()
    crossingsCostsLayout.addRow(QLabel("Select Reference Raster:"), dialog.crossingRefRasterComboBox)

    dialog.crossingCostInput = QLineEdit()
    dialog.crossingCostInput.setPlaceholderText("Enter cost where crossing is present")
    dialog.crossingCostInput.setText("3")
    crossingsCostsLayout.addRow(QLabel("Cost for crossing-covered cells:"), dialog.crossingCostInput)

    dialog.crossingNoCostInput = QLineEdit()
    dialog.crossingNoCostInput.setPlaceholderText("Enter cost where crossing is absent")
    dialog.crossingNoCostInput.setText("1")
    crossingsCostsLayout.addRow(QLabel("Cost for non-crossing cells:"), dialog.crossingNoCostInput)

    outputCrossingLayout = add_output_path_row(
        dialog, "crossingOutputPath", "crossingBrowse", "tif", "Choose output path for Crossings Costs Raster"
    )
    crossingsCostsLayout.addRow(outputCrossingLayout)

    dialog.runCreateRasterFromCrossingButton = QPushButton("Create Crossings Costs Raster")
    crossingsCostsLayout.addRow(dialog.runCreateRasterFromCrossingButton)

    layout.addRow(make_group_box("Create Crossings Costs Raster", crossingsCostsLayout))

    # ============================================================
    # Section 2: Create Number of Crossings Raster (N)
    # ============================================================
    nRasterLayout = QFormLayout()

    dialog.nCrossingVectorComboBox = QComboBox()
    nRasterLayout.addRow(QLabel("Select Crossings Vector:"), dialog.nCrossingVectorComboBox)

    dialog.nCrossingRefRasterComboBox = QComboBox()
    nRasterLayout.addRow(QLabel("Select Reference Raster:"), dialog.nCrossingRefRasterComboBox)

    outputNLayout = add_output_path_row(
        dialog, "nCrossingOutputPath", "nCrossingBrowse", "tif", "Choose output path for N Raster"
    )
    nRasterLayout.addRow(outputNLayout)

    dialog.runCreateNRasterButton = QPushButton("Create Number of Crossings Raster")
    nRasterLayout.addRow(dialog.runCreateNRasterButton)

    layout.addRow(make_group_box("Create Number of Crossings Raster (N)", nRasterLayout))


def connect_crossings_signals(dialog: "AnalysisDialog"):
    """Connects signals for the Crossings tab."""
    dialog.runCreateRasterFromCrossingButton.clicked.connect(
        lambda checked: run_task(
            dialog,
            "Create Crossings Costs Raster",
            work=_crossings_cost_work,
            prepare=_crossings_cost_prepare,
            publish=_crossings_cost_publish,
        )
    )
    dialog.runCreateNRasterButton.clicked.connect(
        lambda checked: run_task(
            dialog,
            "Create Number of Crossings Raster",
            work=_n_raster_work,
            prepare=_n_raster_prepare,
            publish=_n_raster_publish,
        )
    )


# ── Create Crossings Costs Raster ─────────────────────────────────────────────


def _crossings_cost_prepare(dialog: "AnalysisDialog") -> dict:
    """Main thread: read widgets, resolve the vector + reference raster to inputs."""
    crossing_layer = layer_from_dropdown(dialog.crossingComboBox)
    ref_layer = layer_from_dropdown(dialog.crossingRefRasterComboBox)
    output_path = dialog.crossingOutputPath.text().strip()
    crossing_cost = float(dialog.crossingCostInput.text())
    no_crossing_cost = float(dialog.crossingNoCostInput.text())

    if not crossing_layer or not ref_layer or not output_path:
        raise ValueError("Please specify vector, reference raster and output path.")

    ext = ref_layer.extent()
    return {
        "crossing_path": get_layer_path(crossing_layer),
        "extent": (ext.xMinimum(), ext.xMaximum(), ext.yMinimum(), ext.yMaximum()),
        "width": ref_layer.width(),
        "height": ref_layer.height(),
        "output_path": output_path,
        "crossing_cost": crossing_cost,
        "no_crossing_cost": no_crossing_cost,
        "log": lambda msg: dialog.log_message(msg, "Crossings"),
    }


def _crossings_cost_work(params: dict) -> str:
    """Background thread: rasterize the crossing vector to a cost raster."""
    return create_crossings_cost_raster(
        params["crossing_path"],
        params["extent"],
        params["width"],
        params["height"],
        params["output_path"],
        params["crossing_cost"],
        params["no_crossing_cost"],
        log=params["log"],
    )


def _crossings_cost_publish(dialog: "AnalysisDialog", output_raster: str):
    """Main thread: load the cost raster into the project."""
    layer_name = os.path.splitext(os.path.basename(output_raster))[0]
    new_layer = QgsRasterLayer(output_raster, layer_name)
    if not new_layer.isValid():
        raise RuntimeError("Failed to load the resulting raster layer.")

    QgsProject.instance().addMapLayer(new_layer)
    dialog.log_message(f"Raster created at {output_raster}", "Crossings")


# ── Create Number of Crossings Raster (N) ─────────────────────────────────────


def _n_raster_prepare(dialog: "AnalysisDialog") -> dict:
    """Main thread: read widgets, resolve the vector + reference raster to inputs."""
    crossing_layer = layer_from_dropdown(dialog.nCrossingVectorComboBox)
    ref_layer = layer_from_dropdown(dialog.nCrossingRefRasterComboBox)
    output_path = dialog.nCrossingOutputPath.text().strip()

    if not crossing_layer or not ref_layer or not output_path:
        raise ValueError("Please specify crossing vector, reference raster, and output path.")

    if not isinstance(crossing_layer, QgsVectorLayer):
        raise ValueError("Crossing layer must be a vector layer.")

    if not isinstance(ref_layer, QgsRasterLayer):
        raise ValueError("Reference layer must be a raster layer.")

    ext = ref_layer.extent()
    return {
        "crossing_path": get_layer_path(crossing_layer),
        "extent": (ext.xMinimum(), ext.xMaximum(), ext.yMinimum(), ext.yMaximum()),
        "width": ref_layer.width(),
        "height": ref_layer.height(),
        "crs_wkt": ref_layer.crs().toWkt(),
        "output_path": output_path,
        "log": lambda msg: dialog.log_message(msg, "Crossings"),
    }


def _n_raster_work(params: dict) -> dict:
    """Background thread: count crossings per cell and write the N raster."""
    return create_n_crossings_raster(
        params["crossing_path"],
        params["extent"],
        params["width"],
        params["height"],
        params["crs_wkt"],
        params["output_path"],
        log=params["log"],
    )


def _n_raster_publish(dialog: "AnalysisDialog", result: dict):
    """Main thread: load the N raster into the project."""
    output_path = result["output_path"]
    max_count = result["max_count"]

    layer_name = os.path.splitext(os.path.basename(output_path))[0]
    new_layer = QgsRasterLayer(output_path, layer_name)
    if not new_layer.isValid():
        raise RuntimeError("Failed to load the resulting N raster layer.")

    QgsProject.instance().addMapLayer(new_layer)
    dialog.log_message(f"✓ N Raster created successfully at: {output_path}", "Crossings")
    dialog.log_message(f"  Value range: 0 to {max_count} crossings per cell", "Crossings")
