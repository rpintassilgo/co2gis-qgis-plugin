import os
from typing import TYPE_CHECKING

from qgis.PyQt.QtWidgets import QComboBox, QFormLayout, QLabel, QPushButton

from ..core.lcp import combine_rasters_with_comet_formula, run_r_cost, run_r_drain_and_vectorize
from ..task_manager import run_in_background
from ..utils import layer_from_dropdown
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
    finalFileLayout = add_output_path_row(
        dialog, "finalPath", "finalBrowse", "gpkg", "Choose output path for LCP Vector"
    )
    lcpPathLayout.addRow(finalFileLayout)
    dialog.final_button = QPushButton("Create Least Cost Path")
    lcpPathLayout.addRow(dialog.final_button)
    layout.addWidget(make_group_box("Create Least Cost Path", lcpPathLayout))


def connect_lcp_signals(dialog: "AnalysisDialog"):
    """Connects signals for the LCP tab."""
    dialog.combine_button.clicked.connect(lambda checked: run_in_background(dialog, run_raster_combination))
    dialog.final_button.clicked.connect(lambda checked: run_in_background(dialog, run_lcp_creation))


def run_raster_combination(dialog: "AnalysisDialog"):
    """Combine Cost Rasters using COMET formula with N factor"""
    try:
        # Load all layers
        costs_layer = layer_from_dropdown(dialog.combineLandUseDropdown)
        slope_layer = layer_from_dropdown(dialog.combineSlopeDropdown)
        corridors_layer = layer_from_dropdown(dialog.combineCorridorsDropdown)
        crossings_layer = layer_from_dropdown(dialog.combineCrossingsDropdown)
        N_layer = layer_from_dropdown(dialog.combineNRasterDropdown)
        output_path = dialog.combinedRasterPath.text().strip()

        if not output_path:
            raise ValueError("Output path must be specified.")

        dialog.log_message("Combining Cost Rasters using COMET formula: Fc × Fs × [Flu × (1-0.1N) + 0.1N × Fci]", "LCP")
        combine_rasters_with_comet_formula(
            costs_layer,
            slope_layer,
            corridors_layer,
            crossings_layer,
            N_layer,
            output_path,
            log=lambda msg: dialog.log_message(msg, "LCP"),
        )
        dialog.log_message(f"Combined Raster created successfully at: {output_path}", "LCP")

    except Exception as e:
        dialog.log_message(f"Combining Cost Rasters Failed: {str(e)}", "LCP")


def run_lcp_creation(dialog: "AnalysisDialog"):
    """Generate Least Cost Path Vector"""
    try:
        points_layer = layer_from_dropdown(dialog.pointsComboBox)
        combined_layer = layer_from_dropdown(dialog.lcpInputDropdown)
        vector_output_path = dialog.finalPath.text().strip()

        if not all([points_layer, combined_layer, vector_output_path]):
            raise ValueError("All input layers and output path must be specified.")

        # Create temporary paths for intermediate files
        import tempfile

        temp_dir = tempfile.mkdtemp()
        cost_output_path = os.path.join(temp_dir, "cost_surface.tif")
        direction_output_path = os.path.join(temp_dir, "direction_surface.tif")

        # Extract origin and destination
        coords = []
        for feat in points_layer.getFeatures():
            geom = feat.geometry()
            pt = geom.asPoint() if not geom.isMultipart() else geom.asMultiPoint()[0]
            coords.append((pt.x(), pt.y()))
        if len(coords) < 2:
            raise ValueError("Need at least two points (origin, destination) for LCP.")

        origin_str = f"{coords[0][0]:.6f},{coords[0][1]:.6f}"
        dest_str = f"{coords[1][0]:.6f},{coords[1][1]:.6f}"
        dialog.log_message(f"Using origin: {origin_str}", "LCP")
        dialog.log_message(f"Using destination: {dest_str}", "LCP")

        dialog.log_message("Running r.cost to compute cost surface...", "LCP")
        dialog.log_message(f"Cost raster: {combined_layer.source()}", "LCP")
        dialog.log_message(f"Start point: {origin_str}", "LCP")

        cost_result = run_r_cost(combined_layer.source(), origin_str, cost_output_path, direction_output_path)
        dialog.log_message("r.cost completed successfully.", "LCP")

        dialog.log_message("Running r.drain to extract least cost path...", "LCP")
        dialog.log_message(f"Destination point: {dest_str}", "LCP")

        run_r_drain_and_vectorize(
            cost_result, dest_str, vector_output_path, log=lambda msg: dialog.log_message(msg, "LCP")
        )
        dialog.log_message(f"Least Cost Path generated at: {vector_output_path}", "LCP")

        # Cleanup temporary files
        import shutil

        try:
            shutil.rmtree(temp_dir)
        except BaseException:
            pass  # Don't fail if cleanup fails

    except Exception as e:
        dialog.log_message(f"LCP Creation Process Failed: {e}", "LCP")
