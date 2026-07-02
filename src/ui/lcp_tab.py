import os
import tempfile
from typing import TYPE_CHECKING

from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer
from qgis.PyQt.QtWidgets import QComboBox, QFormLayout, QLabel, QPushButton

from ..core.lcp import FACTOR_NAMES, combine_rasters_with_comet_formula, run_r_cost, run_r_drain_and_vectorize
from ..task_manager import run_task
from ..utils import get_layer_path, layer_from_dropdown
from ..widgets.browse_row import add_output_path_row, make_group_box

if TYPE_CHECKING:
    from ..analysis_dialog import AnalysisDialog


def setup_lcp_tab(dialog: "AnalysisDialog", layout: QFormLayout):
    """Sets up the LCP (Least Cost Path) tab."""
    # Combined Costs GroupBox
    combinedCostsLayout = QFormLayout()
    dialog.combineLandUseDropdown = QComboBox()
    dialog.combineSlopeDropdown = QComboBox()
    dialog.combineCorridorsDropdown = QComboBox()
    dialog.combineCrossingsDropdown = QComboBox()
    dialog.combineNRasterDropdown = QComboBox()
    combinedCostsLayout.addRow(QLabel("Select Land Use Costs Raster (F<sub>lu</sub>):"), dialog.combineLandUseDropdown)
    combinedCostsLayout.addRow(QLabel("Select Slope Costs Raster (F<sub>s</sub>):"), dialog.combineSlopeDropdown)
    combinedCostsLayout.addRow(
        QLabel("Select Corridors Costs Raster (F<sub>c</sub>):"), dialog.combineCorridorsDropdown
    )
    combinedCostsLayout.addRow(
        QLabel("Select Crossings Costs Raster (F<sub>ci</sub>):"), dialog.combineCrossingsDropdown
    )
    combinedCostsLayout.addRow(QLabel("Select Number of Crossings Raster (N):"), dialog.combineNRasterDropdown)
    combinedFileLayout = add_output_path_row(
        dialog, "combinedRasterPath", "combinedRasterBrowse", "tif", "Choose output path for Combined Raster"
    )
    combinedCostsLayout.addRow(combinedFileLayout)
    dialog.combine_button = QPushButton("Create Combined Raster")
    combinedCostsLayout.addRow(dialog.combine_button)
    layout.addWidget(make_group_box("Create Combined Costs Raster", combinedCostsLayout))

    # LCP GroupBox
    lcpPathLayout = QFormLayout()
    dialog.pointsComboBox = QComboBox()
    lcpPathLayout.addRow(QLabel("Select Point Vector Layer:"), dialog.pointsComboBox)
    dialog.lcpInputDropdown = QComboBox()
    lcpPathLayout.addRow(QLabel("Select Combined Raster:"), dialog.lcpInputDropdown)
    # Optional r.cost byproducts: only saved + loaded if a path is given, else kept in temp.
    costFileLayout = add_output_path_row(
        dialog,
        "costRasterPath",
        "costRasterBrowse",
        "tif",
        "Choose output path for Cumulative Cost Raster (optional)",
    )
    lcpPathLayout.addRow(costFileLayout)
    directionFileLayout = add_output_path_row(
        dialog,
        "directionRasterPath",
        "directionRasterBrowse",
        "tif",
        "Choose output path for Movement Directions Raster (optional, diagnostic)",
    )
    lcpPathLayout.addRow(directionFileLayout)
    drainFileLayout = add_output_path_row(
        dialog,
        "drainRasterPath",
        "drainRasterBrowse",
        "tif",
        "Choose output path for Drain Raster (optional, diagnostic — rasterized route pre-thinning)",
    )
    lcpPathLayout.addRow(drainFileLayout)
    finalFileLayout = add_output_path_row(
        dialog, "finalPath", "finalBrowse", "gpkg", "Choose output path for LCP Vector"
    )
    lcpPathLayout.addRow(finalFileLayout)
    dialog.final_button = QPushButton("Create Least Cost Path")
    lcpPathLayout.addRow(dialog.final_button)
    layout.addWidget(make_group_box("Create Least Cost Path", lcpPathLayout))


def connect_lcp_signals(dialog: "AnalysisDialog"):
    """Connects signals for the LCP tab."""
    dialog.combine_button.clicked.connect(
        lambda checked: run_task(
            dialog, "Combine Cost Rasters", work=_combine_work, prepare=_combine_prepare, publish=_combine_publish
        )
    )
    dialog.final_button.clicked.connect(
        lambda checked: run_task(dialog, "Create LCP", work=_lcp_work, prepare=_lcp_prepare, publish=_lcp_publish)
    )


# ── Combine cost rasters ──────────────────────────────────────────────────────


def _combine_prepare(dialog: "AnalysisDialog") -> dict:
    """Main thread: read widgets, resolve selected rasters to paths + metadata."""
    combos = {
        "Land Use (Flu)": dialog.combineLandUseDropdown,
        "Slope (Fs)": dialog.combineSlopeDropdown,
        "Corridors (Fc)": dialog.combineCorridorsDropdown,
        "Crossings (Fci)": dialog.combineCrossingsDropdown,
        "N (count)": dialog.combineNRasterDropdown,
    }
    output_path = dialog.combinedRasterPath.text().strip()
    if not output_path:
        raise ValueError("Output path must be specified.")

    slots = {}
    target_crs_wkt = None
    for name in FACTOR_NAMES:
        layer = layer_from_dropdown(combos[name])
        if layer and layer.isValid():
            ext = layer.extent()
            slots[name] = {
                "path": get_layer_path(layer),
                "name": layer.name(),
                "extent": (ext.xMinimum(), ext.xMaximum(), ext.yMinimum(), ext.yMaximum()),
                "res": layer.rasterUnitsPerPixelX(),
            }
            if target_crs_wkt is None:
                target_crs_wkt = layer.crs().toWkt()
        else:
            slots[name] = None

    if not any(slots.values()):
        raise ValueError("At least one cost raster must be provided.")

    dialog.log_message("Combining Cost Rasters using COMET formula: Fc × Fs × [Flu × (1-0.1N) + 0.1N × Fci]", "LCP")
    return {
        "slots": slots,
        "output_path": output_path,
        "target_crs_wkt": target_crs_wkt,
        "log": lambda msg: dialog.log_message(msg, "LCP"),
    }


def _combine_work(params: dict) -> str:
    """Background thread: resample + apply COMET formula, write the raster."""
    return combine_rasters_with_comet_formula(
        params["slots"], params["output_path"], params["target_crs_wkt"], log=params["log"]
    )


def _combine_publish(dialog: "AnalysisDialog", output_path: str):
    """Main thread: load the combined raster into the project."""
    layer_name = os.path.splitext(os.path.basename(output_path))[0]
    layer = QgsRasterLayer(output_path, layer_name)
    if not layer.isValid():
        raise RuntimeError("Failed to load the combined cost raster")
    QgsProject.instance().addMapLayer(layer)
    dialog.log_message(f"Combined Raster created successfully at: {output_path}", "LCP")


# ── Least cost path ───────────────────────────────────────────────────────────


def _lcp_prepare(dialog: "AnalysisDialog") -> dict:
    """Main thread: read points + combined raster, extract origin/destination."""
    points_layer = layer_from_dropdown(dialog.pointsComboBox)
    combined_layer = layer_from_dropdown(dialog.lcpInputDropdown)
    vector_output = dialog.finalPath.text().strip()

    if not all([points_layer, combined_layer, vector_output]):
        raise ValueError(
            "Point layer, combined raster, and the LCP Vector output path must be specified "
            "(The cumulative-cost, movement-directions and drain raster paths are optional)."
        )

    coords = []
    for feat in points_layer.getFeatures():
        geom = feat.geometry()
        pt = geom.asPoint() if not geom.isMultipart() else geom.asMultiPoint()[0]
        coords.append((pt.x(), pt.y()))
    if len(coords) < 2:
        raise ValueError("Need at least two points (origin, destination) for LCP.")

    origin = f"{coords[0][0]:.6f},{coords[0][1]:.6f}"
    dest = f"{coords[1][0]:.6f},{coords[1][1]:.6f}"

    log = lambda msg: dialog.log_message(msg, "LCP")  # noqa: E731
    log(f"Using origin: {origin}")
    log(f"Using destination: {dest}")
    return {
        "origin": origin,
        "dest": dest,
        "combined_path": combined_layer.source(),
        "vector_output": vector_output,
        "cost_output": dialog.costRasterPath.text().strip() or None,
        "direction_output": dialog.directionRasterPath.text().strip() or None,
        "drain_output": dialog.drainRasterPath.text().strip() or None,
        "memory": dialog.rcost_memory_mb,
        "log": log,
    }


def _lcp_work(params: dict) -> dict:
    """Background thread: run the GRASS r.cost → r.drain → r.to.vect chain.

    The r.cost cumulative-cost and movement-direction surfaces are always needed by r.drain.
    When the user gave an output path for one, it is written there (persistent) and reported so
    ``publish`` can load it; otherwise it goes to a temp dir and is discarded after r.drain.
    """
    log = params["log"]
    temp_dir = tempfile.mkdtemp()
    cost_output_path = params["cost_output"] or os.path.join(temp_dir, "cost_surface.tif")
    direction_output_path = params["direction_output"] or os.path.join(temp_dir, "direction_surface.tif")

    log("Running r.cost to compute cost surface...")
    log(f"Cost raster: {params['combined_path']}")
    log(f"Start point: {params['origin']}")
    log(f"r.cost memory budget: {params['memory']} MB")
    cost_result = run_r_cost(
        params["combined_path"], params["origin"], cost_output_path, direction_output_path, memory=params["memory"]
    )
    log("r.cost completed successfully.")

    log(f"Destination point: {params['dest']}")
    vector_output = run_r_drain_and_vectorize(
        cost_result, params["dest"], params["vector_output"], drain_output=params["drain_output"], log=log
    )

    import shutil

    shutil.rmtree(temp_dir, ignore_errors=True)
    return {
        "vector_output": vector_output,
        "cost_output": params["cost_output"],
        "direction_output": params["direction_output"],
        "drain_output": params["drain_output"],
    }


def _lcp_publish(dialog: "AnalysisDialog", result: dict):
    """Main thread: load the LCP vector plus any optional r.cost rasters into the project."""
    vector_output = result["vector_output"]
    layer_name = os.path.splitext(os.path.basename(vector_output))[0]
    layer = QgsVectorLayer(vector_output, layer_name, "ogr")
    if not layer.isValid():
        raise RuntimeError(f"Failed to load LCP vector: {vector_output}")
    QgsProject.instance().addMapLayer(layer)
    dialog.log_message(f"Least Cost Path generated at: {vector_output}", "LCP")

    for path, label in (
        (result.get("cost_output"), "Cumulative Cost"),
        (result.get("direction_output"), "Movement Directions"),
        (result.get("drain_output"), "Drain Raster"),
    ):
        if not path:
            continue
        raster_name = os.path.splitext(os.path.basename(path))[0]
        raster_layer = QgsRasterLayer(path, raster_name)
        if raster_layer.isValid():
            QgsProject.instance().addMapLayer(raster_layer)
            dialog.log_message(f"{label} raster saved and loaded: {path}", "LCP")
        else:
            dialog.log_message(f"Warning: {label} raster saved but failed to load: {path}", "LCP")
