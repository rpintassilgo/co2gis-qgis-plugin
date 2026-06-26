"""Auxiliary-tool domain logic: vector merge + raster clip.

Pure domain — no Qt widgets, no dialog, no ``QgsProject`` writes and no
symbology handling. Inputs are plain values / source paths captured on the main
thread; outputs are written to disk and their paths returned, so the caller can
add them to the project (and copy symbology) from the main thread (the 3-phase
task contract, #2). Progress is reported through an optional ``log(msg)``
callback (bridged to the thread-safe ``dialog.log_message``).

Raster resampling lives in :func:`src.core.raster.resample_raster` and is reused
directly by the Aux tab — it is not duplicated here.
"""

from osgeo import gdal
from qgis import processing


def combine_vectors(layer_paths, output_path, log=lambda msg: None) -> str:
    """Merge vector layers into one with ``native:mergevectorlayers``.

    :param layer_paths: list of source paths/URIs for the layers to merge.
    :param output_path: destination path for the merged vector.
    :returns: the written output path. Does NOT touch the project — the caller
        adds the layer from the main thread.
    """
    log("Combining vector layers...")

    # Use the modern QGIS processing algorithm for merging vectors
    params = {"LAYERS": list(layer_paths), "OUTPUT": output_path}

    result = processing.run("native:mergevectorlayers", params)

    if not result or "OUTPUT" not in result:
        raise RuntimeError("Vector merge processing failed to return the expected output.")

    log("Vectors combined successfully.")
    return result["OUTPUT"]


def clip_raster_to_vector(raster_path, vector_extent, output_path, clip_mode="xy", log=lambda msg: None) -> str:
    """Clip a raster to a vector extent (buffered) with ``gdal:cliprasterbyextent``.

    :param raster_path: path to the raster to clip.
    :param vector_extent: the vector's extent as ``(xmin, ymin, xmax, ymax)`` —
        captured on the main thread (no live layer touched here).
    :param output_path: output path for the clipped raster.
    :param clip_mode: ``"xy"`` (clip both dimensions), ``"x"`` (clip X only, keep
        full Y), ``"y"`` (clip Y only, keep full X).
    :returns: the written output path. Does NOT touch the project — the caller
        adds the layer (and copies symbology) from the main thread.
    """
    if not all([raster_path, vector_extent, output_path]):
        raise ValueError("Raster path, vector extent, and output path must be provided.")

    v_xmin, v_ymin, v_xmax, v_ymax = vector_extent

    # Get the raster's original extent
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

    # Add a buffer around the extent to ensure points are well within the clipped raster
    # Use 10% of the extent size as buffer, with a minimum of 1000 units
    buffer_distance = max((v_xmax - v_xmin) * 0.1, 1000)

    # Build the clipping extent based on mode (PROJWIN string: "xmin,xmax,ymin,ymax")
    if clip_mode == "xy":
        # Clip both X and Y (default behavior)
        clip_xmin = v_xmin - buffer_distance
        clip_xmax = v_xmax + buffer_distance
        clip_ymin = v_ymin - buffer_distance
        clip_ymax = v_ymax + buffer_distance
    elif clip_mode == "x":
        # Clip X only, keep full Y extent from original raster
        clip_xmin = v_xmin - buffer_distance
        clip_xmax = v_xmax + buffer_distance
        clip_ymin = raster_ymin
        clip_ymax = raster_ymax
    elif clip_mode == "y":
        # Clip Y only, keep full X extent from original raster
        clip_xmin = raster_xmin
        clip_xmax = raster_xmax
        clip_ymin = v_ymin - buffer_distance
        clip_ymax = v_ymax + buffer_distance
    else:
        raise ValueError(f"Invalid clip_mode: {clip_mode}. Must be 'xy', 'x', or 'y'.")

    clipped_extent = f"{clip_xmin},{clip_xmax},{clip_ymin},{clip_ymax}"

    params = {
        "INPUT": raster_path,
        "PROJWIN": clipped_extent,
        "NODATA": None,
        "OUTPUT": output_path,
    }

    result = processing.run("gdal:cliprasterbyextent", params)

    if result and "OUTPUT" in result:
        return result["OUTPUT"]
    raise RuntimeError("gdal:cliprasterbyextent processing failed")
