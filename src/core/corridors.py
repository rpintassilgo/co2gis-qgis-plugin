"""Corridors cost-raster domain logic.

Pure domain — no Qt widgets, no dialog, no ``QgsProject`` access. Inputs are
plain values / source paths captured on the main thread; the output raster is
written to disk and its path returned, so the caller adds it to the project from
the main thread (the 3-phase task contract, #2). Progress is reported through an
optional ``log(msg)`` callback (bridged to the thread-safe ``dialog.log_message``).
"""

import os

import numpy as np
from osgeo import gdal
from qgis import processing

from .raster import resample_raster


def create_corridor_cost_raster_with_buffers(
    corridor_path,
    land_use_path,
    land_use_crs,
    ref_path,
    water_ids,
    present_offshore_cost,
    present_onshore_cost,
    absent_offshore_cost,
    absent_onshore_cost,
    buffer_distance,
    output_path,
    log=lambda msg: None,
):
    """Create corridor cost raster with buffer zones and proper water/land detection.

    :param corridor_path: source path of the corridor vector layer.
    :param land_use_path: source path of the land-use raster.
    :param land_use_crs: WKT (or CRS) of the land-use raster, used as ``SOURCE_CRS``.
    :param ref_path: source path of the reference raster (defines grid + extent).
    :param water_ids: set of land-use class values treated as water bodies.
    :returns: ``output_path`` (the written cost raster). Does NOT touch the
        project — the caller adds the layer from the main thread.
    """
    log(f"Creating corridor buffer zones ({buffer_distance}m)...")

    # Step 1: Create buffered corridor zones
    temp_buffered_corridors = output_path.replace(".tif", "_temp_buffered_corridors.gpkg")

    buffer_params = {
        "INPUT": corridor_path,
        "DISTANCE": buffer_distance,
        "SEGMENTS": 5,
        "END_CAP_STYLE": 0,  # Round
        "JOIN_STYLE": 0,  # Round
        "MITER_LIMIT": 2,
        "DISSOLVE": False,  # Dissolve overlapping buffers
        "OUTPUT": temp_buffered_corridors,
    }

    processing.run("native:buffer", buffer_params)

    # Step 2: Create base cost raster with water/land detection for "absent" costs
    ref_ds = gdal.Open(ref_path)
    width, height = ref_ds.RasterXSize, ref_ds.RasterYSize
    geotrans = ref_ds.GetGeoTransform()
    proj = ref_ds.GetProjection()
    extent = f"{geotrans[0]},{geotrans[0] + width * geotrans[1]},{geotrans[3] + height * geotrans[5]},{geotrans[3]}"

    # Step 3: Resample land use to match reference grid
    temp_lu_path = output_path.replace(".tif", "_temp_lu_aligned.tif")
    resample_raster(
        land_use_path,
        temp_lu_path,
        abs(geotrans[1]),
        source_crs=land_use_crs,
        target_crs=proj,
        target_extent=extent,
    )

    # Load land use data and create base cost raster
    lu_ds = gdal.Open(temp_lu_path)
    lu_data = lu_ds.GetRasterBand(1).ReadAsArray()

    # Create base cost raster: water = absent_offshore, land = absent_onshore
    water_pixels = np.isin(lu_data, list(water_ids))
    base_data = np.where(water_pixels, absent_offshore_cost, absent_onshore_cost).astype(np.float32)

    log(
        f"Base costs: {np.sum(water_pixels)} water pixels (cost: {absent_offshore_cost}), "
        f"{np.sum(~water_pixels)} land pixels (cost: {absent_onshore_cost})"
    )

    # Step 4: Create corridor buffer mask
    temp_corridor_mask = output_path.replace(".tif", "_temp_corridor_mask.tif")
    mask_params = {
        "INPUT": temp_buffered_corridors,
        "FIELD": None,
        "BURN": 1,
        "USE_Z": False,
        "UNITS": 0,
        "WIDTH": width,
        "HEIGHT": height,
        "EXTENT": extent,
        "INIT": 0,
        "DATA_TYPE": 1,  # Byte
        "OUTPUT": temp_corridor_mask,
    }

    log("Rasterizing corridor buffer zones...")
    processing.run("gdal:rasterize", mask_params)

    # Load corridor mask
    mask_ds = gdal.Open(temp_corridor_mask)
    mask_data = mask_ds.GetRasterBand(1).ReadAsArray()

    # Step 5: Apply costs ONLY within corridor buffer zones
    corridor_pixels = mask_data == 1
    water_pixels = np.isin(lu_data, list(water_ids))

    # Count pixels for logging
    total_corridor_pixels = np.sum(corridor_pixels)
    offshore_pixels = np.sum(corridor_pixels & water_pixels)
    onshore_pixels = np.sum(corridor_pixels & ~water_pixels)

    log(f"Corridor buffer zones cover {total_corridor_pixels} pixels")
    log(f"  - {offshore_pixels} offshore pixels (cost: {present_offshore_cost})")
    log(f"  - {onshore_pixels} onshore pixels (cost: {present_onshore_cost})")

    if total_corridor_pixels == 0:
        log("WARNING: No corridor pixels found! Check buffer distance and vector layer.")

    # Apply corridor costs ONLY where corridors exist
    base_data[corridor_pixels & water_pixels] = present_offshore_cost  # Corridor + Water
    base_data[corridor_pixels & ~water_pixels] = present_onshore_cost  # Corridor + Land
    # Everything else remains cost = 1.0 (neutral)

    # Step 6: Write final raster
    driver = gdal.GetDriverByName("GTiff")
    out_ds = driver.Create(output_path, width, height, 1, gdal.GDT_Float32, options=["COMPRESS=LZW", "BIGTIFF=YES"])
    out_ds.SetGeoTransform(geotrans)
    out_ds.SetProjection(proj)
    out_ds.GetRasterBand(1).WriteArray(base_data)

    # Cleanup
    out_ds = None
    ref_ds = None
    lu_ds = None
    mask_ds = None

    # Remove temp files
    for temp_file in [temp_lu_path, temp_corridor_mask, temp_buffered_corridors]:
        try:
            os.remove(temp_file)
        except BaseException:
            pass

    log("Corridor cost raster created successfully")
    return output_path
