import os
from typing import TYPE_CHECKING

import numpy as np
from osgeo import gdal
from qgis import processing
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer
from qgis.PyQt.QtWidgets import QComboBox, QFormLayout, QLabel, QLineEdit, QPushButton

from ..task_manager import run_in_background
from ..utils import layer_from_dropdown
from ..widgets.browse_row import add_output_path_row, make_group_box

if TYPE_CHECKING:
    from ..analysis_dialog import AnalysisDialog


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

    layout.addWidget(make_group_box("Create Crossings Costs Raster", crossingsCostsLayout))

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

    layout.addWidget(make_group_box("Create Number of Crossings Raster (N)", nRasterLayout))


def connect_crossings_signals(dialog: "AnalysisDialog"):
    """Connects signals for the Crossings tab."""
    dialog.runCreateRasterFromCrossingButton.clicked.connect(
        lambda checked: run_in_background(dialog, run_crossings_cost_creation)
    )
    dialog.runCreateNRasterButton.clicked.connect(lambda checked: run_in_background(dialog, run_n_raster_creation))


def run_crossings_cost_creation(dialog: "AnalysisDialog"):
    """Create a single-band cost raster from a vector, aligned to a reference raster"""
    try:
        # Get selected layers and parameters
        crossing_layer = layer_from_dropdown(dialog.crossingComboBox)
        ref_layer = layer_from_dropdown(dialog.crossingRefRasterComboBox)
        output_path = dialog.crossingOutputPath.text().strip()
        crossing_cost = float(dialog.crossingCostInput.text())
        no_crossing_cost = float(dialog.crossingNoCostInput.text())

        if not crossing_layer or not ref_layer or not output_path:
            raise ValueError("Please specify vector, reference raster and output path.")

        dialog.log_message("Creating Crossings Costs Raster...", "Crossings")

        # Rasterize: initialize all cells with no_crossing_cost, then burn crossing_cost where features exist
        params = {
            "INPUT": crossing_layer,
            "FIELD": None,
            "BURN": crossing_cost,
            "USE_Z": False,
            "UNITS": 0,  # Pixel units for width/height
            "WIDTH": ref_layer.width(),
            "HEIGHT": ref_layer.height(),
            "EXTENT": ref_layer.extent(),
            "INIT": no_crossing_cost,
            "DATA_TYPE": 5,  # Float32 for single band
            "EXTRA": "",  # Extra GDAL flags if needed
            "OUTPUT": output_path,
        }
        # Use GDAL rasterize for explicit single-band control
        result = processing.run("gdal:rasterize", params)

        # Validate and load
        if not result or "OUTPUT" not in result:
            raise RuntimeError("Rasterization failed to return output.")

        output_raster = result["OUTPUT"]
        if not output_raster:
            raise RuntimeError("Rasterization returned no output.")

        layer_name = os.path.splitext(os.path.basename(output_raster))[0]
        new_layer = QgsRasterLayer(output_raster, layer_name)
        if not new_layer.isValid():
            raise RuntimeError("Failed to load the resulting raster layer.")

        QgsProject.instance().addMapLayer(new_layer)
        dialog.log_message(f"Raster created at {output_path}", "Crossings")

    except Exception as e:
        dialog.log_message(f"Crossings raster creation failed: {e}", "Crossings")


def run_n_raster_creation(dialog: "AnalysisDialog"):
    """
    Create a raster where each cell contains the COUNT of how many times
    the crossing vector intersects that cell.

    Algorithm:
    1. Rasterize vector to reference raster extent/resolution
    2. For each cell, count the number of line segments passing through it
    3. Output: Integer raster with intersection counts (0, 1, 2, 3, ...)
    """
    try:
        # Get selected layers
        crossing_layer = layer_from_dropdown(dialog.nCrossingVectorComboBox)
        ref_layer = layer_from_dropdown(dialog.nCrossingRefRasterComboBox)
        output_path = dialog.nCrossingOutputPath.text().strip()

        if not crossing_layer or not ref_layer or not output_path:
            raise ValueError("Please specify crossing vector, reference raster, and output path.")

        if not isinstance(crossing_layer, QgsVectorLayer):
            raise ValueError("Crossing layer must be a vector layer.")

        if not isinstance(ref_layer, QgsRasterLayer):
            raise ValueError("Reference layer must be a raster layer.")

        dialog.log_message("Creating Number of Crossings Raster (N)...", "Crossings")

        # Get reference raster properties
        ref_extent = ref_layer.extent()
        ref_width = ref_layer.width()
        ref_height = ref_layer.height()
        ref_crs = ref_layer.crs()

        dialog.log_message(f"  Reference raster: {ref_width}x{ref_height} pixels", "Crossings")
        dialog.log_message(
            f"  Extent: [{ref_extent.xMinimum():.2f}, {ref_extent.xMaximum():.2f}, {ref_extent.yMinimum():.2f}, {ref_extent.yMaximum():.2f}]",
            "Crossings",
        )

        # Calculate cell size
        cell_width = (ref_extent.xMaximum() - ref_extent.xMinimum()) / ref_width
        cell_height = (ref_extent.yMaximum() - ref_extent.yMinimum()) / ref_height

        dialog.log_message(f"  Cell size: {cell_width:.2f} x {cell_height:.2f}", "Crossings")

        # Initialize a dictionary to track unique features per cell
        # Key: (row, col), Value: set of feature IDs
        cell_features = {}

        # Iterate through all features in the crossing vector
        feature_count = crossing_layer.featureCount()
        dialog.log_message(f"  Processing {feature_count} features...", "Crossings")

        processed = 0
        for feature in crossing_layer.getFeatures():
            feature_id = feature.id()
            geom = feature.geometry()

            if not geom or geom.isEmpty():
                continue

            # Get all line segments (handles MultiLineString)
            if geom.isMultipart():
                lines = geom.asMultiPolyline()
            else:
                lines = [geom.asPolyline()]

            # Track cells touched by THIS feature (to avoid counting same feature multiple times)
            cells_touched_by_feature = set()

            # For each line segment
            for line in lines:
                if len(line) < 2:
                    continue

                # Process each segment between consecutive points
                for i in range(len(line) - 1):
                    x1, y1 = line[i].x(), line[i].y()
                    x2, y2 = line[i + 1].x(), line[i + 1].y()

                    # Get all cells intersected by this line segment
                    cells = get_intersected_cells(
                        x1,
                        y1,
                        x2,
                        y2,
                        ref_extent.xMinimum(),
                        ref_extent.yMaximum(),
                        cell_width,
                        cell_height,
                        ref_width,
                        ref_height,
                    )

                    # Mark these cells as touched by this feature
                    for col, row in cells:
                        cells_touched_by_feature.add((row, col))

            # Now register this feature ID in all cells it touched
            for cell_key in cells_touched_by_feature:
                if cell_key not in cell_features:
                    cell_features[cell_key] = set()
                cell_features[cell_key].add(feature_id)

            processed += 1
            if processed % 100 == 0:
                dialog.log_message(f"  Processed {processed}/{feature_count} features...", "Crossings")

        dialog.log_message(f"  All {feature_count} features processed", "Crossings")

        # Convert the dictionary to a count array
        dialog.log_message("  Building count array from unique features...", "Crossings")
        count_array = np.zeros((ref_height, ref_width), dtype=np.int32)

        for (row, col), feature_set in cell_features.items():
            count_array[row, col] = len(feature_set)

        # Log statistics
        max_count = np.max(count_array)
        cells_with_crossings = np.sum(count_array > 0)
        total_cells = ref_width * ref_height

        dialog.log_message(f"  Max crossings per cell: {max_count}", "Crossings")
        dialog.log_message(
            f"  Cells with crossings: {cells_with_crossings:,} / {total_cells:,} ({100 * cells_with_crossings / total_cells:.1f}%)",
            "Crossings",
        )

        # Create output raster
        dialog.log_message("  Writing output raster...", "Crossings")

        driver = gdal.GetDriverByName("GTiff")
        out_ds = driver.Create(
            output_path, ref_width, ref_height, 1, gdal.GDT_Int32, options=["COMPRESS=LZW", "BIGTIFF=YES"]
        )

        # Set geotransform and projection
        geotransform = [ref_extent.xMinimum(), cell_width, 0, ref_extent.yMaximum(), 0, -cell_height]
        out_ds.SetGeoTransform(geotransform)
        out_ds.SetProjection(ref_crs.toWkt())

        # Write data
        out_band = out_ds.GetRasterBand(1)
        out_band.WriteArray(count_array)
        out_band.SetNoDataValue(-9999)
        out_band.FlushCache()

        # Close dataset
        out_ds = None

        # Load into QGIS
        layer_name = os.path.splitext(os.path.basename(output_path))[0]
        new_layer = QgsRasterLayer(output_path, layer_name)
        if not new_layer.isValid():
            raise RuntimeError("Failed to load the resulting N raster layer.")

        QgsProject.instance().addMapLayer(new_layer)
        dialog.log_message(f"✓ N Raster created successfully at: {output_path}", "Crossings")
        dialog.log_message(f"  Value range: 0 to {max_count} crossings per cell", "Crossings")

    except Exception as e:
        dialog.log_message(f"N Raster creation failed: {e}", "Crossings")


def get_intersected_cells(x1, y1, x2, y2, origin_x, origin_y, cell_width, cell_height, grid_width, grid_height):
    """
    Get all raster cells intersected by a line segment using a rasterization algorithm.

    Parameters:
        x1, y1, x2, y2: Line segment endpoints in map coordinates
        origin_x, origin_y: Top-left corner of raster (origin_y is top)
        cell_width, cell_height: Cell dimensions
        grid_width, grid_height: Raster dimensions in cells

    Returns:
        List of (col, row) tuples
    """
    cells = set()

    # Convert endpoints to cell coordinates
    col1 = int((x1 - origin_x) / cell_width)
    row1 = int((origin_y - y1) / cell_height)
    col2 = int((x2 - origin_x) / cell_width)
    row2 = int((origin_y - y2) / cell_height)

    # Bresenham's line algorithm (adapted for cells)
    dx = abs(col2 - col1)
    dy = abs(row2 - row1)

    col = col1
    row = row1

    col_inc = 1 if col2 > col1 else -1
    row_inc = 1 if row2 > row1 else -1

    # Add cells along the line
    if dx > dy:
        error = dx / 2
        while col != col2:
            if 0 <= col < grid_width and 0 <= row < grid_height:
                cells.add((col, row))
            error -= dy
            if error < 0:
                row += row_inc
                error += dx
            col += col_inc
    else:
        error = dy / 2
        while row != row2:
            if 0 <= col < grid_width and 0 <= row < grid_height:
                cells.add((col, row))
            error -= dx
            if error < 0:
                col += col_inc
                error += dy
            row += row_inc

    # Add final cell
    if 0 <= col2 < grid_width and 0 <= row2 < grid_height:
        cells.add((col2, row2))

    return list(cells)
