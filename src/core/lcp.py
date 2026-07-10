"""Least-cost-path domain logic: COMET raster combination + the GRASS routing chain.

Pure domain — no Qt widgets, no dialog, no ``QgsProject`` writes. Inputs are
plain values / source paths captured on the main thread; outputs are written to
disk and their paths returned, so the caller can add them to the project from the
main thread (the 3-phase task contract, #2). Progress is reported through an
optional ``log(msg)`` callback (bridged to the thread-safe ``dialog.log_message``).
"""

import gc
import os
import shutil
import tempfile

import numpy as np
from osgeo import gdal
from qgis import processing
from qgis.core import QgsRasterLayer

from ..constants.comet import COST_FLOOR, N_CAP
from ..constants.lcp import DEFAULT_RCOST_MEMORY_MB
from .comet import comet_cell_cost
from .raster import resample_present_to_common_grid

# Canonical COMET factor slots, in formula order.
FACTOR_NAMES = ["Land Use (Flu)", "Slope (Fs)", "Corridors (Fc)", "Crossings (Fci)", "N (count)"]


def grass_alg_id(name: str) -> str:
    """
    Resolve a GRASS processing algorithm id across QGIS versions.

    QGIS 3.x registers GRASS algorithms under the ``grass7:`` prefix; QGIS 4.x
    renamed the provider to ``grass:``. Probe the processing registry and return
    whichever prefix is actually available, preferring the modern ``grass:``
    form and falling back to it when neither is found.

    :param name: algorithm name without prefix, e.g. ``"r.cost"``.
    """
    from qgis.core import QgsApplication

    registry = QgsApplication.processingRegistry()
    for prefix in ("grass", "grass7"):
        alg_id = f"{prefix}:{name}"
        if registry.algorithmById(alg_id) is not None:
            return alg_id
    return f"grass:{name}"


def combine_rasters_with_comet_formula(slots: dict, output_path: str, target_crs_wkt, log=lambda msg: None) -> str:
    """
    Combine cost rasters with the COMET formula: Fc × Fs × [Flu × (1-0.1N) + 0.1N × Fci]

    :param slots: maps each name in :data:`FACTOR_NAMES` to either ``None`` (absent,
        treated as constant 1.0) or a dict ``{"path", "name", "extent", "res"}``
        captured on the main thread. ``extent`` is ``(xmin, xmax, ymin, ymax)``.
    :param target_crs_wkt: WKT of the reference CRS to reproject every raster to.
    :returns: ``output_path`` (the written combined raster). Does NOT touch the
        project — the caller adds the layer from the main thread.

    N is capped at :data:`~src.constants.comet.N_CAP` for stability; the result is
    floored at :data:`~src.constants.comet.COST_FLOOR` so r.drain works.
    """
    present = [(name, slots[name]) for name in FACTOR_NAMES if slots.get(name)]

    for name in FACTOR_NAMES:
        meta = slots.get(name)
        if meta:
            log(f"  {name}: {meta['name']} - Valid")
        else:
            log(f"  ⚠️ {name}: Not selected - will use constant 1.0")

    if not present:
        raise ValueError("At least one cost raster must be provided!")

    # Resample every present raster onto the shared grid (intersection extent, first raster's
    # resolution), reprojected to the project CRS. Into a private temp dir (not the user's output
    # folder) so a mid-loop failure never leaves _resampled_*.tif scaffolding behind — the finally
    # cleans it up.
    log("Step 1: Resampling rasters to a common grid...")
    temp_dir = tempfile.mkdtemp()
    try:
        resampled_data = resample_present_to_common_grid(present, target_crs_wkt, temp_dir, "_resampled_", log)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    # Get dimensions
    meta = resampled_data["_meta"]
    width, height = meta["width"], meta["height"]
    geotrans, proj = meta["geotrans"], meta["proj"]

    log("Step 3: Applying COMET formula...")

    # Create arrays with default value 1.0 for missing layers
    Flu = resampled_data.get("Land Use (Flu)", np.ones((height, width), dtype=np.float32))
    Fs = resampled_data.get("Slope (Fs)", np.ones((height, width), dtype=np.float32))
    Fc = resampled_data.get("Corridors (Fc)", np.ones((height, width), dtype=np.float32))
    Fci = resampled_data.get("Crossings (Fci)", np.ones((height, width), dtype=np.float32))
    N = resampled_data.get("N (count)", np.ones((height, width), dtype=np.float32))

    # Log value ranges
    log(f"  Flu range: [{np.min(Flu):.2f}, {np.max(Flu):.2f}]")
    log(f"  Fs range: [{np.min(Fs):.2f}, {np.max(Fs):.2f}]")
    log(f"  Fc range: [{np.min(Fc):.2f}, {np.max(Fc):.2f}]")
    log(f"  Fci range: [{np.min(Fci):.2f}, {np.max(Fci):.2f}]")
    log(f"  N range (before cap): [{np.min(N):.2f}, {np.max(N):.2f}]")

    # Cap N (critical for formula stability)
    N_capped = np.minimum(N, N_CAP)

    if np.max(N) > N_CAP:
        num_capped = np.sum(N > N_CAP)
        log(f"  ⚠️ {num_capped:,} pixels had N > {N_CAP} and were capped to {N_CAP}")

    log(f"  N range (after cap): [{np.min(N_capped):.2f}, {np.max(N_capped):.2f}]")

    # Apply COMET formula: Fc × Fs × [Flu × (1 - 0.1N) + 0.1N × Fci]
    log(f"  Calculating formula for {width * height:,} pixels...")
    output_data = comet_cell_cost(Fc, Fs, Flu, Fci, N_capped)
    log("  ✓ Formula applied successfully")

    # Log final cost range
    log(f"  Combined cost range: [{np.min(output_data):.2f}, {np.max(output_data):.2f}]")

    # Ensure minimum cost > 0 (avoid issues with r.drain)
    output_data = np.maximum(output_data, COST_FLOOR)

    # Write final output
    log("Step 4: Writing output raster...")
    driver = gdal.GetDriverByName("GTiff")
    out_ds = driver.Create(output_path, width, height, 1, gdal.GDT_Float32, options=["COMPRESS=LZW", "BIGTIFF=YES"])
    out_ds.SetGeoTransform(geotrans)
    out_ds.SetProjection(proj)
    out_band = out_ds.GetRasterBand(1)
    out_band.WriteArray(output_data)
    out_band.FlushCache()
    out_band = None
    out_ds.FlushCache()
    out_ds = None
    log(f"  ✓ Raster written to: {os.path.basename(output_path)}")

    # Force memory cleanup
    log("  Cleaning up memory...")
    output_data = None
    Flu = None
    Fs = None
    Fc = None
    Fci = None
    N = None
    N_capped = None
    resampled_data = None
    gc.collect()

    log("✓ Combined cost raster computed using COMET formula")
    return output_path


def run_r_cost(
    input_raster: str,
    start_coordinates: str,
    cost_output: str,
    direction_output: str,
    memory: int = DEFAULT_RCOST_MEMORY_MB,
    start_raster: str = None,
) -> dict:
    """
    Runs the r.cost GRASS algorithm.

    The origin is either ``start_coordinates`` (a GRASS ``"x,y"`` string — the single-point case) or,
    when ``start_raster`` is given, every non-null cell of that raster (multi-origin — used by the
    greedy network tree, where accumulation starts from the whole already-built network).

    ``memory`` is the RAM budget (MB) handed to r.cost; larger values speed up big rasters
    but must fit in available memory. Callers pass the user-configured value; the default
    is the shared ``constants.lcp.DEFAULT_RCOST_MEMORY_MB``.
    """
    # 1) Make sure output folders exist
    for path in (cost_output, direction_output):
        d = os.path.dirname(path)
        if d and not os.path.exists(d):
            os.makedirs(d, exist_ok=True)

    # 2) Read the raster to set the GRASS region
    rlayer = QgsRasterLayer(input_raster, "temp")
    if not rlayer.isValid():
        raise RuntimeError(f"Invalid cost raster: {input_raster}")
    ext = rlayer.extent()
    region = f"{ext.xMinimum()},{ext.xMaximum()},{ext.yMinimum()},{ext.yMaximum()}"

    # 3) Build parameters for r.cost — origin is a start raster (multi-cell) or start coordinates.
    params = {
        "input": input_raster,
        "-n": True,  # Use Knight's move
        "max_cost": 0,  # no maximum cost
        "memory": memory,  # RAM budget (MB) for large rasters; set via the Settings dialog
        "output": cost_output,
        "outdir": direction_output,
        "GRASS_REGION_PARAMETER": region,
        "GRASS_REGION_CELLSIZE_PARAMETER": 0,
    }
    if start_raster:
        params["start_raster"] = start_raster
    else:
        params["start_coordinates"] = start_coordinates

    # 4) Run r.cost to generate cost accumulation and direction surfaces
    result = processing.run(grass_alg_id("r.cost"), params)

    if not result:
        raise RuntimeError("r.cost processing failed")

    # 5) Return the result for downstream use
    return {"output": cost_output, "outdir": direction_output}


def run_r_drain_and_vectorize(
    cost_result: dict, dest_coord: str, vector_output: str, drain_output: str = None, log=lambda msg: None
) -> str:
    """
    Extract the LCP with r.drain → r.thin → r.to.vect.

    Writes the route to ``vector_output`` and returns its path. Does NOT load it
    into the project — the caller adds the layer from the main thread.

    ``drain_output`` optionally persists the raw r.drain raster (the rasterized route
    *before* r.thin) to that path so the caller can load it as a diagnostic layer; when
    ``None`` it goes to a temp dir and is discarded.
    """
    for path in (vector_output, drain_output):
        d = os.path.dirname(path) if path else None
        if d and not os.path.exists(d):
            os.makedirs(d, exist_ok=True)

    temp_dir = tempfile.mkdtemp()
    try:
        # r.drain needs the accumulation raster (cost_result['output']) and start from DESTINATION.
        # It traces the steepest descent (lowest cost) to the source encoded by r.cost.
        accum_path = cost_result["output"]
        direction_path = cost_result["outdir"]

        if not os.path.exists(accum_path):
            raise RuntimeError(f"Cost accumulation raster not found: {accum_path}")
        if not os.path.exists(direction_path):
            raise RuntimeError(f"Direction raster not found: {direction_path}")

        # r.drain → raster path, then r.to.vect lines to GPKG. The raw drain raster is persisted to
        # ``drain_output`` when given (so it survives temp cleanup), else kept in temp and discarded.
        drain_out = drain_output or os.path.join(temp_dir, "drain_path.tif")
        thin_out = os.path.join(temp_dir, "drain_thin.tif")

        # Get the region from the accumulation raster to use in r.drain
        accum_layer = QgsRasterLayer(accum_path, "temp_accum")
        if not accum_layer.isValid():
            raise RuntimeError(f"Cannot read accumulation raster: {accum_path}")

        ext = accum_layer.extent()
        region = f"{ext.xMinimum()},{ext.xMaximum()},{ext.yMinimum()},{ext.yMaximum()}"

        log("Running r.drain to extract least cost path...")

        # Run r.drain from destination to trace back to origin
        # CRITICAL: Must pass direction raster from r.cost to follow the cost path correctly
        # CRITICAL 2: Must set GRASS_REGION to avoid "North must be larger than South" error
        drain_result = processing.run(
            grass_alg_id("r.drain"),
            {
                "input": accum_path,
                "direction": direction_path,
                "start_coordinates": dest_coord,
                "output": drain_out,
                "GRASS_REGION_PARAMETER": region,
                "GRASS_REGION_CELLSIZE_PARAMETER": 0,
            },
        )

        if not drain_result or "output" not in drain_result:
            raise RuntimeError("r.drain failed to produce output")

        drain_path = drain_result["output"]

        log(f"r.drain output: {drain_path}")
        log("Running r.thin to prepare for vectorization...")

        # Thin the raster path to avoid "crowded cell" errors in r.to.vect
        thin_result = processing.run(
            grass_alg_id("r.thin"),
            {
                "input": drain_path,
                "output": thin_out,
                "iterations": 200,  # Sufficient iterations to thin properly
            },
        )

        if not thin_result or "output" not in thin_result:
            raise RuntimeError("r.thin failed to produce output")

        thin_path = thin_result["output"]

        log(f"r.thin output: {thin_path}")
        log("Converting to vector...")

        # Convert thinned raster path to vector lines
        processing.run(
            grass_alg_id("r.to.vect"),
            {
                "input": thin_path,
                "type": 0,  # line
                "output": vector_output,
            },
        )

        log("✓ LCP created successfully using: r.drain → r.thin → r.to.vect")
        return vector_output
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
