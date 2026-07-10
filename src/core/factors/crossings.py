"""Crossings domain logic: rasterize a crossing vector to a cost raster and
count crossings per cell (the COMET N raster).

Pure domain — no Qt widgets, no dialog, no ``QgsProject`` writes. Inputs are
plain values / source paths captured on the main thread; outputs are written to
disk and their paths returned, so the caller adds them to the project from the
main thread (the 3-phase task contract, #2). Progress is reported through an
optional ``log(msg)`` callback (bridged to the thread-safe ``dialog.log_message``).
"""

import numpy as np
from osgeo import gdal
from qgis import processing
from qgis.core import QgsVectorLayer

from ..raster import get_intersected_cells


def create_crossings_cost_raster(
    crossing_path: str,
    extent,
    width: int,
    height: int,
    output_path: str,
    crossing_cost: float,
    no_crossing_cost: float,
    log=lambda msg: None,
) -> str:
    """Create a single-band cost raster from a vector, aligned to a reference raster.

    :param crossing_path: source path of the crossing vector.
    :param extent: reference grid extent as ``(xmin, xmax, ymin, ymax)``.
    :param width, height: reference grid size in pixels.
    :param crossing_cost: value burned where features exist.
    :param no_crossing_cost: value used to initialise every cell.
    :returns: the written raster path. Does NOT touch the project.
    """
    log("Creating Crossings Costs Raster...")

    xmin, xmax, ymin, ymax = extent

    # Rasterize: initialize all cells with no_crossing_cost, then burn crossing_cost where features exist
    params = {
        "INPUT": crossing_path,
        "FIELD": None,
        "BURN": crossing_cost,
        "USE_Z": False,
        "UNITS": 0,  # Pixel units for width/height
        "WIDTH": width,
        "HEIGHT": height,
        "EXTENT": f"{xmin},{xmax},{ymin},{ymax}",
        "INIT": no_crossing_cost,
        "DATA_TYPE": 5,  # Float32 for single band
        "EXTRA": "",  # Extra GDAL flags if needed
        "OUTPUT": output_path,
    }
    # Use GDAL rasterize for explicit single-band control
    result = processing.run("gdal:rasterize", params)

    # Validate
    if not result or "OUTPUT" not in result:
        raise RuntimeError("Rasterization failed to return output.")

    output_raster = result["OUTPUT"]
    if not output_raster:
        raise RuntimeError("Rasterization returned no output.")

    return output_raster


def create_n_crossings_raster(
    crossing_path: str,
    extent,
    width: int,
    height: int,
    crs_wkt: str,
    output_path: str,
    log=lambda msg: None,
) -> dict:
    """Create a raster where each cell contains the COUNT of how many times the
    crossing vector intersects that cell.

    Algorithm:
    1. Walk every feature, rasterizing its line segments onto the reference grid.
    2. For each cell, count the number of distinct features passing through it.
    3. Output: Integer raster with intersection counts (0, 1, 2, 3, ...)

    :param crossing_path: source path of the crossing vector.
    :param extent: reference grid extent as ``(xmin, xmax, ymin, ymax)``.
    :param width, height: reference grid size in pixels.
    :param crs_wkt: WKT of the reference CRS to stamp on the output.
    :returns: ``{"output_path", "max_count"}``. Does NOT touch the project.
    """
    log("Creating Number of Crossings Raster (N)...")

    xmin, xmax, ymin, ymax = extent
    ref_width = width
    ref_height = height

    log(f"  Reference raster: {ref_width}x{ref_height} pixels")
    log(f"  Extent: [{xmin:.2f}, {xmax:.2f}, {ymin:.2f}, {ymax:.2f}]")

    # Calculate cell size
    cell_width = (xmax - xmin) / ref_width
    cell_height = (ymax - ymin) / ref_height

    log(f"  Cell size: {cell_width:.2f} x {cell_height:.2f}")

    # Open the crossing vector from its source path (no project access).
    crossing_layer = QgsVectorLayer(crossing_path, "crossings", "ogr")
    if not crossing_layer.isValid():
        raise RuntimeError(f"Failed to load crossing vector: {crossing_path}")

    # Initialize a dictionary to track unique features per cell
    # Key: (row, col), Value: set of feature IDs
    cell_features = {}

    # Iterate through all features in the crossing vector
    feature_count = crossing_layer.featureCount()
    log(f"  Processing {feature_count} features...")

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
                    xmin,
                    ymax,
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
            log(f"  Processed {processed}/{feature_count} features...")

    log(f"  All {feature_count} features processed")

    # Convert the dictionary to a count array
    log("  Building count array from unique features...")
    count_array = np.zeros((ref_height, ref_width), dtype=np.int32)

    for (row, col), feature_set in cell_features.items():
        count_array[row, col] = len(feature_set)

    # Log statistics
    max_count = np.max(count_array)
    cells_with_crossings = np.sum(count_array > 0)
    total_cells = ref_width * ref_height

    log(f"  Max crossings per cell: {max_count}")
    log(
        f"  Cells with crossings: {cells_with_crossings:,} / {total_cells:,} "
        f"({100 * cells_with_crossings / total_cells:.1f}%)"
    )

    # Create output raster
    log("  Writing output raster...")

    driver = gdal.GetDriverByName("GTiff")
    out_ds = driver.Create(
        output_path, ref_width, ref_height, 1, gdal.GDT_Int32, options=["COMPRESS=LZW", "BIGTIFF=YES"]
    )

    # Set geotransform and projection
    geotransform = [xmin, cell_width, 0, ymax, 0, -cell_height]
    out_ds.SetGeoTransform(geotransform)
    out_ds.SetProjection(crs_wkt)

    # Write data
    out_band = out_ds.GetRasterBand(1)
    out_band.WriteArray(count_array)
    out_band.SetNoDataValue(-9999)
    out_band.FlushCache()

    # Close dataset
    out_ds = None

    return {"output_path": output_path, "max_count": int(max_count)}
