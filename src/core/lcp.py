"""Least-cost-path domain logic: COMET raster combination + the GRASS routing chain.

Pure domain — no Qt widgets, no dialog. Progress is reported through an optional
``log(msg)`` callback so the UI can bridge it to its log panel while these
functions stay importable and testable on their own.
"""

import gc
import os
import shutil
import tempfile

import numpy as np
from osgeo import gdal
from qgis import processing
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer

from ..constants.comet import COST_FLOOR, N_CAP
from .comet import comet_cell_cost
from .raster import resample_raster


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


def combine_rasters_with_comet_formula(
    land_use_layer, slope_layer, corridors_layer, crossings_layer, N_layer, output_path: str, log=lambda msg: None
) -> str:
    """
    Combines rasters using COMET formula: Fc × Fs × [Flu × (1-0.1N) + 0.1N × Fci]

    Parameters:
        land_use_layer: Flu (land use costs)
        slope_layer: Fs (slope costs)
        corridors_layer: Fc (corridor costs)
        crossings_layer: Fci (crossing costs)
        N_layer: N (number of infrastructure crossings per cell)

    Any layer can be None - will be treated as constant 1.0 (neutral)
    N is capped at 10 to avoid negative Flu coefficients and numerical instability
    """

    # Collect valid layers
    all_layers = []
    layer_names = ["Land Use (Flu)", "Slope (Fs)", "Corridors (Fc)", "Crossings (Fci)", "N (count)"]
    layer_map = {}

    for idx, (layer, name) in enumerate(
        zip([land_use_layer, slope_layer, corridors_layer, crossings_layer, N_layer], layer_names)
    ):
        if layer and layer.isValid():
            all_layers.append(layer)
            layer_map[name] = idx
            log(f"  {name}: {layer.name()} - Valid")
        else:
            log(f"  ⚠️ {name}: Not selected - will use constant 1.0")

    if not all_layers:
        raise ValueError("At least one cost raster must be provided!")

    # Calculate common extent
    log("Step 1: Calculating common extent...")
    common_extent = all_layers[0].extent()
    for layer in all_layers[1:]:
        common_extent = common_extent.intersect(layer.extent())

    if common_extent.isEmpty():
        raise ValueError("No common extent found - rasters do not overlap!")

    # Use first valid layer as reference for resolution
    reference_layer = all_layers[0]
    ref_resolution = reference_layer.rasterUnitsPerPixelX()
    log(f"Using resolution: {ref_resolution:.2f}m from {reference_layer.name()}")

    # Resample all valid layers
    log("Step 2: Resampling rasters...")
    resampled_data = {}

    valid_layers_to_resample = [
        (layer, name)
        for layer, name in zip([land_use_layer, slope_layer, corridors_layer, crossings_layer, N_layer], layer_names)
        if layer and layer.isValid()
    ]

    total_layers = len(valid_layers_to_resample)
    current_layer = 0

    for layer, name in valid_layers_to_resample:
        current_layer += 1
        log(f"  Resampling {current_layer}/{total_layers}: {name}...")

        resampled_path = os.path.join(os.path.dirname(output_path), f"_resampled_{name.replace(' ', '_')}.tif")

        resampled_output = resample_raster(
            layer,
            resampled_path,
            ref_resolution,
            source_crs=layer.crs(),
            target_crs=reference_layer.crs(),
            target_extent=f"{common_extent.xMinimum()},{common_extent.xMaximum()},{common_extent.yMinimum()},{common_extent.yMaximum()}",
        )

        if resampled_output:
            ds = gdal.Open(resampled_output)
            if ds is None:
                raise RuntimeError(f"Failed to open resampled raster for {layer.name()}")

            band = ds.GetRasterBand(1)
            data = band.ReadAsArray().astype(np.float32)

            # Get dimensions from first raster
            if not resampled_data:
                width = ds.RasterXSize
                height = ds.RasterYSize
                geotrans = ds.GetGeoTransform()
                proj = ds.GetProjection()
                resampled_data["_meta"] = {"width": width, "height": height, "geotrans": geotrans, "proj": proj}
                log(f"  Target grid: {width}x{height} pixels ({width * height:,} total cells)")

            resampled_data[name] = data

            # Properly close GDAL dataset
            band = None
            ds = None

            # Clean up temp file
            try:
                if os.path.exists(resampled_output):
                    os.remove(resampled_output)
            except Exception as cleanup_error:
                log(f"  ⚠️ Could not delete temp file: {cleanup_error}")
        else:
            raise RuntimeError(f"Failed to resample {layer.name()}")

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

    # Log warnings for missing layers
    if "Land Use (Flu)" not in resampled_data:
        log("  ⚠️ Land Use (Flu) not selected - assuming Flu=1.0 (neutral)")
    if "Slope (Fs)" not in resampled_data:
        log("  ⚠️ Slope (Fs) not selected - assuming Fs=1.0 (neutral)")
    if "Corridors (Fc)" not in resampled_data:
        log("  ⚠️ Corridors (Fc) not selected - assuming Fc=1.0 (neutral)")
    if "Crossings (Fci)" not in resampled_data:
        log("  ⚠️ Crossings (Fci) not selected - assuming Fci=1.0 (neutral)")
    if "N (count)" not in resampled_data:
        log("  ⚠️ N (count) not selected - assuming N=1.0 (one infrastructure per cell)")

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

    log("Step 5: Loading result into QGIS...")
    # Load result into QGIS
    layer_name = os.path.splitext(os.path.basename(output_path))[0]
    new_layer = QgsRasterLayer(output_path, layer_name)
    if new_layer.isValid():
        QgsProject.instance().addMapLayer(new_layer)
        log("✓ Successfully created combined cost raster using COMET formula")
        return output_path
    else:
        raise RuntimeError("Failed to load the combined cost raster")


def run_r_cost(input_raster: str, start_coordinates: str, cost_output: str, direction_output: str) -> dict:
    """
    Runs the r.cost GRASS algorithm using start coordinates.
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

    # 3) Build parameters for r.cost - use start_points for the origin
    params = {
        "input": input_raster,
        "start_coordinates": start_coordinates,  # Use start_points for r.cost
        "-n": True,  # Use Knight's move
        "max_cost": 0,  # no maximum cost
        "memory": 8000,  # Increased memory for large rasters (8GB)
        "output": cost_output,
        "outdir": direction_output,
        "GRASS_REGION_PARAMETER": region,
        "GRASS_REGION_CELLSIZE_PARAMETER": 0,
    }

    # 4) Run r.cost to generate cost accumulation and direction surfaces
    result = processing.run(grass_alg_id("r.cost"), params)

    if not result:
        raise RuntimeError("r.cost processing failed")

    # 5) Return the result for downstream use
    return {"output": cost_output, "outdir": direction_output}


def run_r_drain_and_vectorize(cost_result: dict, dest_coord: str, vector_output: str, log=lambda msg: None) -> None:
    """
    Simple LCP extraction using r.drain → r.to.vect.
    Proven to work reliably based on successful logs.
    """
    out_dir = os.path.dirname(vector_output)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    temp_dir = tempfile.mkdtemp()

    # r.drain needs the accumulation raster (cost_result['output']) and start from DESTINATION.
    # It traces the steepest descent (lowest cost) to the source encoded by r.cost.
    accum_path = cost_result["output"]
    direction_path = cost_result["outdir"]

    if not os.path.exists(accum_path):
        raise RuntimeError(f"Cost accumulation raster not found: {accum_path}")
    if not os.path.exists(direction_path):
        raise RuntimeError(f"Direction raster not found: {direction_path}")

    # r.drain → raster path, then r.to.vect lines to GPKG
    drain_out = os.path.join(temp_dir, "drain_path.tif")
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

    # Load the resulting vector
    layer_name = os.path.splitext(os.path.basename(vector_output))[0]
    layer = QgsVectorLayer(vector_output, layer_name, "ogr")
    if not layer.isValid():
        raise RuntimeError(f"Failed to load LCP vector: {vector_output}")
    QgsProject.instance().addMapLayer(layer)

    log("✓ LCP created successfully using: r.drain → r.thin → r.to.vect")

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)
