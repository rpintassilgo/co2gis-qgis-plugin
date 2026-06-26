from typing import TYPE_CHECKING
from qgis.PyQt.QtWidgets import (
    QLabel, QComboBox, QLineEdit, QPushButton, QHBoxLayout, QFormLayout,
    QGroupBox, QCheckBox, QVBoxLayout, QRadioButton, QButtonGroup
)
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsProject, QgsVectorLayer, QgsRasterLayer, QgsRectangle
import processing
import os

from ..task_manager import run_in_background
from ..utils import select_output_file, update_original_resolution, apply_symbology, get_layer_path

if TYPE_CHECKING:
    from ..analysis_dialog import AnalysisDialog


def setup_aux_tab(dialog: 'AnalysisDialog', layout: QVBoxLayout):
    """Sets up the Aux tab with its various functionalities."""
    # Combine Vectors GroupBox
    combineVectorsGroupBox = QGroupBox()
    combineVectorsGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")
    combineVectorsLayout = QFormLayout()
    combineVectorsTitle = QLabel("Combine Vectors")
    combineVectorsTitle.setAlignment(Qt.AlignCenter)
    combineVectorsTitle.setStyleSheet("font-weight: bold; font-size: 12px;")
    combineVectorsLayout.addRow(combineVectorsTitle)
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
    dialog.vectorsOutputPath = QLineEdit()
    dialog.vectorsOutputPath.setPlaceholderText("Choose output path for Combined Vectors")
    dialog.vectorsBrowse = QPushButton("Browse")
    dialog.vectorsBrowse.clicked.connect(lambda: select_output_file(dialog.vectorsOutputPath, "shp"))
    outputVectorsLayout = QHBoxLayout()
    outputVectorsLayout.addWidget(dialog.vectorsOutputPath)
    outputVectorsLayout.addWidget(dialog.vectorsBrowse)
    combineVectorsLayout.addRow(outputVectorsLayout)
    dialog.runCombineVectorsButton = QPushButton("Combine vectors")
    combineVectorsLayout.addRow(dialog.runCombineVectorsButton)
    combineVectorsGroupBox.setLayout(combineVectorsLayout)
    layout.addWidget(combineVectorsGroupBox)

    # Resample Raster GroupBox
    resampleGroupBox = QGroupBox()
    resampleGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")
    resampleLayout = QFormLayout()
    resampleTitle = QLabel("Resample Raster")
    resampleTitle.setAlignment(Qt.AlignCenter)
    resampleTitle.setStyleSheet("font-weight: bold; font-size: 12px;")
    resampleLayout.addRow(resampleTitle)
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
    dialog.resampleOutputPath = QLineEdit()
    dialog.resampleOutputPath.setPlaceholderText("Choose output path for Resampled Raster")
    dialog.resampleBrowse = QPushButton("Browse")
    dialog.resampleBrowse.clicked.connect(lambda: select_output_file(dialog.resampleOutputPath, "tif"))
    resampleOutputLayout = QHBoxLayout()
    resampleOutputLayout.addWidget(dialog.resampleOutputPath)
    resampleOutputLayout.addWidget(dialog.resampleBrowse)
    resampleLayout.addRow(resampleOutputLayout)
    dialog.runResampleButton = QPushButton("Run Resampling")
    resampleLayout.addRow(dialog.runResampleButton)
    resampleGroupBox.setLayout(resampleLayout)
    layout.addWidget(resampleGroupBox)

    # Clip Raster GroupBox
    clipGroupBox = QGroupBox()
    clipGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")
    clipLayout = QFormLayout()
    clipTitle = QLabel("Clip Raster to Area")
    clipTitle.setAlignment(Qt.AlignCenter)
    clipTitle.setStyleSheet("font-weight: bold; font-size: 12px;")
    clipLayout.addRow(clipTitle)
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
    dialog.clippedRasterPath = QLineEdit()
    dialog.clippedRasterPath.setPlaceholderText("Choose output path for Clipped Raster")
    dialog.clippedRasterBrowse = QPushButton("Browse")
    dialog.clippedRasterBrowse.clicked.connect(lambda: select_output_file(dialog.clippedRasterPath, "tif"))
    clippedFileLayout = QHBoxLayout()
    clippedFileLayout.addWidget(dialog.clippedRasterPath)
    clippedFileLayout.addWidget(dialog.clippedRasterBrowse)
    clipLayout.addRow(clippedFileLayout)
    dialog.clip_button = QPushButton("Clip Raster to Area")
    clipLayout.addRow(dialog.clip_button)
    clipGroupBox.setLayout(clipLayout)
    layout.addWidget(clipGroupBox)


def connect_aux_signals(dialog: 'AnalysisDialog'):
    """Connects signals for the Aux tab."""
    dialog.runCombineVectorsButton.clicked.connect(lambda checked: run_in_background(dialog, run_vector_combination))
    dialog.resampleRasterComboBox.currentIndexChanged.connect(lambda: update_original_resolution(dialog))
    dialog.runResampleButton.clicked.connect(lambda checked: run_in_background(dialog, run_raster_resampling))
    dialog.clip_button.clicked.connect(lambda checked: run_in_background(dialog, run_raster_clipping))


def run_vector_combination(dialog: 'AnalysisDialog'):
    """Combine two vector layers into one"""
    try:
        layer1 = QgsProject.instance().mapLayer(dialog.vectorComboBox.currentData())
        layer2 = QgsProject.instance().mapLayer(dialog.vector2ComboBox.currentData())
        output_path = dialog.vectorsOutputPath.text().strip()

        if not all([layer1, layer2, output_path]):
            raise ValueError("Both vector layers and an output path must be specified.")

        dialog.log_message("Combining vector layers...", "Aux")

        # Use the modern QGIS processing algorithm for merging vectors
        params = {
            'LAYERS': [layer1, layer2],
            'OUTPUT': output_path
        }

        result = processing.run("native:mergevectorlayers", params)

        if not result or 'OUTPUT' not in result:
            raise RuntimeError("Vector merge processing failed to return the expected output.")

        dialog.log_message("Vectors combined successfully.", "Aux")

        # Load the combined layer
        layer_name = os.path.splitext(os.path.basename(result['OUTPUT']))[0]
        combined_layer = QgsVectorLayer(result['OUTPUT'], layer_name, "ogr")
        if combined_layer.isValid():
            QgsProject.instance().addMapLayer(combined_layer)
            dialog.log_message(f"Combined vector layer loaded with {combined_layer.featureCount()} features.", "Aux")
        else:
            dialog.log_message("Failed to load combined vector layer.", "Aux")

    except Exception as e:
        dialog.log_message(f"Vector Combination Failed: {str(e)}", "Aux")


def run_raster_resampling(dialog: 'AnalysisDialog'):
    """Resample Raster"""
    try:
        raster_layer = QgsProject.instance().mapLayer(dialog.resampleRasterComboBox.currentData())
        target_resolution = float(dialog.targetResolutionInput.text().strip())
        resampling_method_text = dialog.resamplingMethodComboBox.currentText()
        output_path = dialog.resampleOutputPath.text().strip()

        if not all([raster_layer, target_resolution, output_path]):
            raise ValueError("Raster layer, target resolution, and output path must be specified.")

        resampling_map = {
            "Nearest Neighbor": 0, "Bilinear": 1, "Cubic": 2, "Cubic Spline": 3, "Lanczos": 4
        }
        resampling_method = resampling_map.get(resampling_method_text, 0)

        dialog.log_message(f"Resampling raster '{raster_layer.name()}'...", "Aux")
        params = {
            'INPUT': raster_layer,
            'TARGET_RESOLUTION': target_resolution,
            'RESAMPLING': resampling_method,
            'OUTPUT': output_path,
            'EXTRA': '-co COMPRESS=LZW -co BIGTIFF=YES'
        }
        processing.run("gdal:warpreproject", params)
        dialog.log_message(f"Resampled raster saved successfully at: {output_path}", "Aux")

        layer_name = os.path.splitext(os.path.basename(output_path))[0]
        resampled_layer = QgsRasterLayer(output_path, layer_name)
        if resampled_layer.isValid():
            QgsProject.instance().addMapLayer(resampled_layer)
        else:
            dialog.log_message("Failed to load resampled raster.", "Aux")

    except Exception as e:
        dialog.log_message(f"Resampling Raster Failed: {str(e)}", "Aux")


def run_raster_clipping(dialog: 'AnalysisDialog'):
    """Clip Combined Raster"""
    try:
        points_layer = QgsProject.instance().mapLayer(dialog.clipPointVectorComboBox.currentData())
        raster_to_clip = QgsProject.instance().mapLayer(dialog.clipRasterInputDropdown.currentData())
        output_path = dialog.clippedRasterPath.text().strip()

        if not all([points_layer, raster_to_clip, output_path]):
            raise ValueError("Points layer, raster to clip, and output path must be specified.")

        # Get clip mode from radio buttons
        clip_mode_id = dialog.clipModeButtonGroup.checkedId()
        clip_modes = {0: "xy", 1: "x", 2: "y"}
        clip_mode = clip_modes.get(clip_mode_id, "xy")

        mode_names = {"xy": "X and Y", "x": "X only", "y": "Y only"}
        dialog.log_message(f"Clipping Raster (mode: {mode_names[clip_mode]})...", "Aux")
        clip_raster_to_vector(get_layer_path(raster_to_clip), points_layer, output_path, clip_mode)
        dialog.log_message(f"Clipped Raster created successfully at: {output_path}", "Aux")

        layer_name = os.path.splitext(os.path.basename(output_path))[0]
        clipped_layer = QgsRasterLayer(output_path, layer_name)
        if clipped_layer.isValid():
            QgsProject.instance().addMapLayer(clipped_layer)
        else:
            dialog.log_message("Failed to load clipped raster.", "Aux")

        if dialog.copySymbologyCheckbox.isChecked():
            dialog.log_message("Copying symbology from original raster...", "Aux")
            apply_symbology(raster_to_clip, clipped_layer)
            dialog.log_message("Symbology copied successfully.", "Aux")

    except Exception as e:
        dialog.log_message(f"Clipping Raster Failed: {str(e)}", "Aux")


def clip_raster_to_vector(raster_path, vector_layer, output_path, clip_mode="xy"):
    """
    Clips a raster to the extent of a vector layer with a buffer to ensure points are within the raster.

    Args:
        raster_path: Path to the raster to clip
        vector_layer: Vector layer defining the extent
        output_path: Output path for clipped raster
        clip_mode: "xy" (clip both dimensions), "x" (clip X only, keep full Y), "y" (clip Y only, keep full X)
    """
    if not all([raster_path, vector_layer, output_path]):
        raise ValueError("Raster path, vector layer, and output path must be provided.")

    # Get the raster's original extent
    from osgeo import gdal
    raster_ds = gdal.Open(raster_path)
    if not raster_ds:
        raise RuntimeError(f"Could not open raster: {raster_path}")

    raster_geotrans = raster_ds.GetGeoTransform()
    raster_width = raster_ds.RasterXSize
    raster_height = raster_ds.RasterYSize

    # Calculate raster extent
    raster_xmin = raster_geotrans[0]
    raster_ymax = raster_geotrans[3]
    raster_xmax = raster_xmin + raster_width * raster_geotrans[1]
    raster_ymin = raster_ymax + raster_height * raster_geotrans[5]  # geotrans[5] is negative

    raster_ds = None

    # Get the vector extent
    vector_extent = vector_layer.extent()

    # Add a buffer around the extent to ensure points are well within the clipped raster
    # Use 10% of the extent size as buffer, with a minimum of 1000 units
    buffer_distance = max(vector_extent.width() * 0.1, 1000)

    # Build the clipping extent based on mode
    if clip_mode == "xy":
        # Clip both X and Y (default behavior)
        clipped_extent = QgsRectangle(
            vector_extent.xMinimum() - buffer_distance,
            vector_extent.yMinimum() - buffer_distance,
            vector_extent.xMaximum() + buffer_distance,
            vector_extent.yMaximum() + buffer_distance
        )
    elif clip_mode == "x":
        # Clip X only, keep full Y extent from original raster
        clipped_extent = QgsRectangle(
            vector_extent.xMinimum() - buffer_distance,
            raster_ymin,  # Use full raster Y extent
            vector_extent.xMaximum() + buffer_distance,
            raster_ymax
        )
    elif clip_mode == "y":
        # Clip Y only, keep full X extent from original raster
        clipped_extent = QgsRectangle(
            raster_xmin,  # Use full raster X extent
            vector_extent.yMinimum() - buffer_distance,
            raster_xmax,
            vector_extent.yMaximum() + buffer_distance
        )
    else:
        raise ValueError(f"Invalid clip_mode: {clip_mode}. Must be 'xy', 'x', or 'y'.")

    params = {
        'INPUT': raster_path,
        'PROJWIN': clipped_extent,
        'NODATA': None,
        'OUTPUT': output_path,
    }

    result = processing.run("gdal:cliprasterbyextent", params)

    if result and 'OUTPUT' in result:
        return result['OUTPUT']
    else:
        raise RuntimeError("gdal:cliprasterbyextent processing failed")
