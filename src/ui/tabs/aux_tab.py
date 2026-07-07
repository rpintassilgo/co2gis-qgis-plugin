import os
from typing import TYPE_CHECKING

from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer
from qgis.PyQt.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from ...core.aux import clip_raster_to_vector, combine_vectors
from ...core.raster import resample_raster
from ...task_manager import run_task
from ...utils import apply_symbology, get_layer_path, layer_from_dropdown, update_resolution_field
from ...widgets.browse_row import add_output_path_row, make_group_box

if TYPE_CHECKING:
    from ...analysis_dialog import AnalysisDialog


def setup_aux_tab(dialog: "AnalysisDialog", layout: QVBoxLayout):
    """Sets up the Aux tab with its various functionalities."""
    # Combine Vectors GroupBox
    combineVectorsLayout = QFormLayout()
    infoCombineText = QLabel(
        "ⓘ Combine vectors functionality is useful to combine roads and railroads vectors for crossings to calculate crossings cost raster in Corridors and Crossings tab later."
    )
    infoCombineText.setStyleSheet("color: lightgrey; font-size: 11px;")
    infoCombineText.setWordWrap(True)
    combineVectorsLayout.addRow(infoCombineText)
    dialog.vectorComboBox = QComboBox()
    dialog.vector2ComboBox = QComboBox()
    vectorSelectionLayout = QHBoxLayout()
    vectorSelectionLayout.addWidget(dialog.vectorComboBox)
    vectorSelectionLayout.addWidget(dialog.vector2ComboBox)
    combineVectorsLayout.addRow(QLabel("Select Vectors:"), vectorSelectionLayout)
    outputVectorsLayout = add_output_path_row(
        dialog, "vectorsOutputPath", "vectorsBrowse", "shp", "Choose output path for Combined Vectors"
    )
    combineVectorsLayout.addRow(outputVectorsLayout)
    dialog.runCombineVectorsButton = QPushButton("Combine vectors")
    combineVectorsLayout.addRow(dialog.runCombineVectorsButton)
    layout.addWidget(make_group_box("Combine Vectors", combineVectorsLayout))

    # Resample Raster GroupBox
    resampleLayout = QFormLayout()
    infoResampleText = QLabel(
        "ⓘ For accurate GIS analysis, use a raster with a projected CRS (meters) instead of a geographic CRS (degrees), as degrees are not uniform in distance across different latitudes."
    )
    infoResampleText.setStyleSheet("color: lightgrey; font-size: 11px;")
    infoResampleText.setWordWrap(True)
    resampleLayout.addRow(infoResampleText)
    dialog.resampleRasterComboBox = QComboBox()
    resampleLayout.addRow(QLabel("Select Raster to Resample:"), dialog.resampleRasterComboBox)
    dialog.originalResolutionInput = QLineEdit()
    dialog.originalResolutionInput.setPlaceholderText("Original Resolution (auto or manual)")
    resampleLayout.addRow(QLabel("Original Resolution:"), dialog.originalResolutionInput)
    dialog.targetResolutionInput = QLineEdit()
    dialog.targetResolutionInput.setPlaceholderText("Enter Target Resolution")
    resampleLayout.addRow(QLabel("Target Resolution:"), dialog.targetResolutionInput)
    dialog.resamplingMethodComboBox = QComboBox()
    dialog.resamplingMethodComboBox.addItems(["Nearest Neighbor", "Bilinear", "Cubic", "Lanczos"])
    resampleLayout.addRow(QLabel("Resampling Method:"), dialog.resamplingMethodComboBox)
    resampleOutputLayout = add_output_path_row(
        dialog, "resampleOutputPath", "resampleBrowse", "tif", "Choose output path for Resampled Raster"
    )
    resampleLayout.addRow(resampleOutputLayout)
    dialog.runResampleButton = QPushButton("Run Resampling")
    resampleLayout.addRow(dialog.runResampleButton)
    layout.addWidget(make_group_box("Resample Raster", resampleLayout))

    # Clip Raster GroupBox
    clipLayout = QFormLayout()
    infoClipText = QLabel(
        "ⓘ This functionality clips rasters based on a two-point vector layer (like a rectangle between points). It's useful to reduce raster sizes for faster processing. For example, when calculating a new LCP, you can clip DEM and land use rasters to make computations lighter."
    )
    infoClipText.setStyleSheet("color: lightgrey; font-size: 11px;")
    infoClipText.setWordWrap(True)
    clipLayout.addRow(infoClipText)
    dialog.clipPointVectorComboBox = QComboBox()
    clipLayout.addRow(QLabel("Select Point Vector Layer:"), dialog.clipPointVectorComboBox)
    dialog.clipRasterInputDropdown = QComboBox()
    clipLayout.addRow(QLabel("Select Raster To Clip:"), dialog.clipRasterInputDropdown)

    # Clip mode radio buttons
    clipModeLabel = QLabel("Clip Mode:")
    dialog.clipModeButtonGroup = QButtonGroup()
    dialog.clipModeXY = QRadioButton("Clip in X and Y")
    dialog.clipModeX = QRadioButton("Clip in X only")
    dialog.clipModeY = QRadioButton("Clip in Y only")
    dialog.clipModeXY.setChecked(True)  # Default
    dialog.clipModeButtonGroup.addButton(dialog.clipModeXY, 0)
    dialog.clipModeButtonGroup.addButton(dialog.clipModeX, 1)
    dialog.clipModeButtonGroup.addButton(dialog.clipModeY, 2)

    clipModeLayout = QHBoxLayout()
    clipModeLayout.addWidget(dialog.clipModeXY)
    clipModeLayout.addWidget(dialog.clipModeX)
    clipModeLayout.addWidget(dialog.clipModeY)
    clipLayout.addRow(clipModeLabel, clipModeLayout)

    dialog.copySymbologyCheckbox = QCheckBox("Copy Symbology to Clipped Raster")
    dialog.copySymbologyCheckbox.setChecked(False)
    clipLayout.addRow(dialog.copySymbologyCheckbox)
    clippedFileLayout = add_output_path_row(
        dialog, "clippedRasterPath", "clippedRasterBrowse", "tif", "Choose output path for Clipped Raster"
    )
    clipLayout.addRow(clippedFileLayout)
    dialog.clip_button = QPushButton("Clip Raster to Area")
    clipLayout.addRow(dialog.clip_button)
    layout.addWidget(make_group_box("Clip Raster to Area", clipLayout))


def connect_aux_signals(dialog: "AnalysisDialog"):
    """Connects signals for the Aux tab."""
    dialog.runCombineVectorsButton.clicked.connect(
        lambda checked: run_task(
            dialog, "Combine Vectors", work=_combine_work, prepare=_combine_prepare, publish=_combine_publish
        )
    )
    dialog.resampleRasterComboBox.currentIndexChanged.connect(
        lambda: update_resolution_field(dialog, dialog.resampleRasterComboBox, dialog.originalResolutionInput)
    )
    dialog.runResampleButton.clicked.connect(
        lambda checked: run_task(
            dialog, "Resample Raster", work=_resample_work, prepare=_resample_prepare, publish=_resample_publish
        )
    )
    dialog.clip_button.clicked.connect(
        lambda checked: run_task(dialog, "Clip Raster", work=_clip_work, prepare=_clip_prepare, publish=_clip_publish)
    )


# ── Combine vectors ───────────────────────────────────────────────────────────


def _combine_prepare(dialog: "AnalysisDialog") -> dict:
    """Main thread: read widgets, resolve the two vectors to source paths."""
    layer1 = layer_from_dropdown(dialog.vectorComboBox)
    layer2 = layer_from_dropdown(dialog.vector2ComboBox)
    output_path = dialog.vectorsOutputPath.text().strip()

    if not all([layer1, layer2, output_path]):
        raise ValueError("Both vector layers and an output path must be specified.")

    return {
        "layer_paths": [get_layer_path(layer1), get_layer_path(layer2)],
        "output_path": output_path,
        "log": lambda msg: dialog.log_message(msg, "Aux"),
    }


def _combine_work(params: dict) -> str:
    """Background thread: merge the vector layers, return the output path."""
    return combine_vectors(params["layer_paths"], params["output_path"], log=params["log"])


def _combine_publish(dialog: "AnalysisDialog", output_path: str):
    """Main thread: load the combined vector into the project."""
    layer_name = os.path.splitext(os.path.basename(output_path))[0]
    combined_layer = QgsVectorLayer(output_path, layer_name, "ogr")
    if not combined_layer.isValid():
        raise RuntimeError("Failed to load combined vector layer.")
    QgsProject.instance().addMapLayer(combined_layer)
    dialog.log_message(f"Combined vector layer loaded with {combined_layer.featureCount()} features.", "Aux")


# ── Resample raster ───────────────────────────────────────────────────────────


def _resample_prepare(dialog: "AnalysisDialog") -> dict:
    """Main thread: read widgets, resolve the raster to a source path."""
    raster_layer = layer_from_dropdown(dialog.resampleRasterComboBox)
    target_resolution = float(dialog.targetResolutionInput.text().strip())
    resampling_method_text = dialog.resamplingMethodComboBox.currentText()
    output_path = dialog.resampleOutputPath.text().strip()

    if not all([raster_layer, target_resolution, output_path]):
        raise ValueError("Raster layer, target resolution, and output path must be specified.")

    resampling_map = {"Nearest Neighbor": 0, "Bilinear": 1, "Cubic": 2, "Cubic Spline": 3, "Lanczos": 4}
    resampling_method = resampling_map.get(resampling_method_text, 0)

    return {
        "raster_path": get_layer_path(raster_layer),
        "raster_name": raster_layer.name(),
        "output_path": output_path,
        "target_resolution": target_resolution,
        "resampling_method": resampling_method,
        "log": lambda msg: dialog.log_message(msg, "Aux"),
    }


def _resample_work(params: dict) -> str:
    """Background thread: resample the raster, return the output path."""
    log = params["log"]
    output_path = params["output_path"]
    log(f"Resampling raster '{params['raster_name']}'...")
    resample_raster(
        params["raster_path"], output_path, params["target_resolution"], resampling=params["resampling_method"]
    )
    log(f"Resampled raster saved successfully at: {output_path}")
    return output_path


def _resample_publish(dialog: "AnalysisDialog", output_path: str):
    """Main thread: load the resampled raster into the project."""
    layer_name = os.path.splitext(os.path.basename(output_path))[0]
    resampled_layer = QgsRasterLayer(output_path, layer_name)
    if not resampled_layer.isValid():
        raise RuntimeError("Failed to load resampled raster.")
    QgsProject.instance().addMapLayer(resampled_layer)


# ── Clip raster ───────────────────────────────────────────────────────────────


def _clip_prepare(dialog: "AnalysisDialog") -> dict:
    """Main thread: read widgets, resolve the raster path, capture the clip
    extent, mode, copy-symbology flag and the original layer (for publish)."""
    points_layer = layer_from_dropdown(dialog.clipPointVectorComboBox)
    raster_to_clip = layer_from_dropdown(dialog.clipRasterInputDropdown)
    output_path = dialog.clippedRasterPath.text().strip()

    if not all([points_layer, raster_to_clip, output_path]):
        raise ValueError("Points layer, raster to clip, and output path must be specified.")

    # Get clip mode from radio buttons
    clip_mode_id = dialog.clipModeButtonGroup.checkedId()
    clip_modes = {0: "xy", 1: "x", 2: "y"}
    clip_mode = clip_modes.get(clip_mode_id, "xy")

    # Capture the vector extent on the main thread (no live layer in the worker).
    extent = points_layer.extent()
    vector_extent = (extent.xMinimum(), extent.yMinimum(), extent.xMaximum(), extent.yMaximum())

    mode_names = {"xy": "X and Y", "x": "X only", "y": "Y only"}
    log = lambda msg: dialog.log_message(msg, "Aux")  # noqa: E731
    log(f"Clipping Raster (mode: {mode_names[clip_mode]})...")

    return {
        "raster_path": get_layer_path(raster_to_clip),
        "vector_extent": vector_extent,
        "output_path": output_path,
        "clip_mode": clip_mode,
        "copy_symbology": dialog.copySymbologyCheckbox.isChecked(),
        # Keep the original layer reference so publish can re-apply its symbology
        # (reading the live renderer) on the main thread.
        "original_layer": raster_to_clip,
        "log": log,
    }


def _clip_work(params: dict) -> dict:
    """Background thread: clip the raster, carry through what publish needs."""
    output_path = clip_raster_to_vector(
        params["raster_path"],
        params["vector_extent"],
        params["output_path"],
        params["clip_mode"],
        log=params["log"],
    )
    params["log"](f"Clipped Raster created successfully at: {output_path}")
    return {
        "output_path": output_path,
        "copy_symbology": params["copy_symbology"],
        "original_layer": params["original_layer"],
    }


def _clip_publish(dialog: "AnalysisDialog", result: dict):
    """Main thread: load the clipped raster and copy symbology if requested."""
    output_path = result["output_path"]
    layer_name = os.path.splitext(os.path.basename(output_path))[0]
    clipped_layer = QgsRasterLayer(output_path, layer_name)
    if not clipped_layer.isValid():
        raise RuntimeError("Failed to load clipped raster.")
    QgsProject.instance().addMapLayer(clipped_layer)

    if result["copy_symbology"]:
        dialog.log_message("Copying symbology from original raster...", "Aux")
        apply_symbology(result["original_layer"], clipped_layer)
        dialog.log_message("Symbology copied successfully.", "Aux")
