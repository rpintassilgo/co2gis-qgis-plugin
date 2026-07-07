"""Land-use cost raster domain logic.

Pure domain — no Qt widgets, no dialog, no ``QgsProject`` writes. Inputs are
plain values / source paths captured on the main thread; the output is written to
disk and its path returned, so the caller can add it to the project from the main
thread (the 3-phase task contract, #2). Progress is reported through an optional
``log(msg)`` callback (bridged to the thread-safe ``dialog.log_message``).
"""

import numpy as np
from osgeo import gdal


def create_land_use_cost_raster(source_path: str, class_costs: dict, output_path: str, log=lambda msg: None) -> str:
    """Create a land use cost raster from a source raster and a dict of costs.

    :param source_path: filesystem path of the input land-use raster.
    :param class_costs: maps each land-use class id (float) to its cost factor.
    :param output_path: where to write the resulting GeoTIFF.
    :returns: ``output_path`` (the written cost raster). Does NOT touch the
        project — the caller adds the layer from the main thread.
    """
    # Open the input raster
    input_ds = gdal.Open(source_path)
    if not input_ds:
        raise RuntimeError("Could not open input raster with GDAL")

    # Read the input band
    band = input_ds.GetRasterBand(1)
    input_data = band.ReadAsArray()

    # Create output array with same shape
    output_data = np.zeros_like(input_data, dtype=np.float32)

    # Calculate max cost for undefined values
    max_cost = max(class_costs.values()) if class_costs else 0
    undefined_cost = max_cost + 1

    # Set undefined cost as default
    output_data.fill(undefined_cost)

    # Apply costs using numpy operations (much faster than pixel-by-pixel)
    for class_id, cost in class_costs.items():
        output_data[input_data == class_id] = cost

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
