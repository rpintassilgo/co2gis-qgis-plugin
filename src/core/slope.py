"""Slope cost raster domain logic.

Pure domain — no Qt widgets, no dialog, no ``QgsProject`` writes. Inputs are
plain values / source paths captured on the main thread; outputs are written to
disk and their paths returned, so the caller can add them to the project from the
main thread (the 3-phase task contract, #2). Progress is reported through an
optional ``log(msg)`` callback (bridged to the thread-safe ``dialog.log_message``).
"""

import numpy as np
from osgeo import gdal
from qgis import processing


def create_slope_layer_from_dem(dem_path: str, output_path: str, log=lambda msg: None) -> str:
    """Create a slope raster from a DEM using the ``qgis:slope`` algorithm.

    :param dem_path: filesystem path of the input DEM raster.
    :param output_path: where to write the resulting slope GeoTIFF.
    :returns: ``output_path`` (the written slope raster). Does NOT touch the
        project — the caller adds the layer from the main thread.
    """
    if not dem_path:
        raise ValueError("Input DEM layer is not valid.")

    params = {
        "INPUT": dem_path,
        "Z_FACTOR": 1,
        "UNITS": 1,  # Percent
        "OUTPUT": output_path,
    }
    result = processing.run("qgis:slope", params)
    if not result or "OUTPUT" not in result:
        raise RuntimeError("Slope processing failed to return the expected output.")
    return output_path


def create_slope_costs_from_slope(slope_path: str, intervals: list, output_path: str, log=lambda msg: None) -> str:
    """Create a slope cost raster from a slope raster and interval definitions.

    :param slope_path: filesystem path of the input slope raster.
    :param intervals: list of dicts ``{"min", "max", "cost"}`` (``max`` may be
        ``None`` for an open-ended upper bound).
    :param output_path: where to write the resulting cost GeoTIFF.
    :returns: ``output_path`` (the written cost raster). Does NOT touch the
        project — the caller adds the layer from the main thread.
    """
    # Open the input raster
    input_ds = gdal.Open(slope_path)
    if not input_ds:
        raise RuntimeError("Could not open input raster with GDAL")

    # Read the input band
    band = input_ds.GetRasterBand(1)
    slope_data = band.ReadAsArray()

    # Create output array with same shape
    output_data = np.zeros_like(slope_data, dtype=np.float32)

    # Apply costs using numpy operations
    # First set the default cost for slopes above the last interval
    if intervals:
        output_data.fill(intervals[-1]["cost"])

    # Then apply each interval's cost
    for interval in reversed(intervals):  # Process in reverse to handle overlapping ranges correctly
        min_slope = interval["min"]
        max_slope = interval["max"]
        cost = interval["cost"]

        # Create mask for values in this interval
        if max_slope is None:
            mask = slope_data >= min_slope
        else:
            mask = (slope_data >= min_slope) & (slope_data < max_slope)

        # Apply cost to masked areas
        output_data[mask] = cost

    # Create output raster
    driver = gdal.GetDriverByName("GTiff")
    out_ds = driver.Create(
        output_path,
        input_ds.RasterXSize,
        input_ds.RasterYSize,
        1,
        gdal.GDT_Float32,
        options=["COMPRESS=LZW", "NUM_THREADS=ALL_CPUS", "BIGTIFF=YES"],
    )

    # Copy projection and geotransform
    out_ds.SetProjection(input_ds.GetProjection())
    out_ds.SetGeoTransform(input_ds.GetGeoTransform())

    # Write data
    out_band = out_ds.GetRasterBand(1)
    out_band.WriteArray(output_data)

    # Clean up
    out_ds = None
    input_ds = None

    return output_path
