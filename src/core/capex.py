"""CAPEX domain logic: cost-factor sampling along the pipeline + the COMET CAPEX math.

Pure domain — no Qt widgets, no dialog, no ``QgsProject`` access, no live-layer
iteration. Inputs are plain values / source paths / detached geometry captured on
the main thread; rasters are rebuilt from their paths on the background thread when
needed (the 3-phase task contract, #2). Progress is reported through a ``log(msg)``
callback (bridged to the thread-safe ``dialog.log_message``).

Stays consistent with the routing surface (``core.lcp``) by sharing
:func:`~src.core.comet.comet_cell_cost` and :data:`~src.constants.comet.N_CAP`.
"""

import os
import shutil
import tempfile

import numpy as np
from osgeo import gdal
from qgis.core import QgsGeometry, QgsPointXY, QgsRaster, QgsRasterLayer, QgsRectangle

from ..constants.comet import N_CAP
from .comet import comet_cell_cost
from .raster import resample_raster

# Canonical COMET cost-factor slots, in formula order. ``extract_cells`` /
# ``extract_points`` key their inputs by these names.
COST_NAMES = ["Land Use (Flu)", "Slope (Fs)", "Corridors (Fc)", "Crossings (Fci)"]


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


def get_raster_value_at_point(raster_layer, point):
    """Gets a raster value at a specific point."""
    if not raster_layer:
        return None
    provider = raster_layer.dataProvider()
    ident = provider.identify(point, QgsRaster.IdentifyFormatValue)
    if ident.isValid() and ident.results():
        return list(ident.results().values())[0]
    return None


def extract_cells(cost_specs, segments, infra_geoms, log):
    """
    Precise extraction: resample the present cost rasters to a common grid, then
    walk the pipeline cell-by-cell computing the exact length within each cell
    (Lcell) and counting infrastructure crossings (N) per cell.

    :param cost_specs: dict ``name -> {"path", "crs_wkt", "extent", "res", "name"}``
        for the PRESENT cost rasters only. ``name`` is one of :data:`COST_NAMES`;
        ``extent`` is ``(xmin, xmax, ymin, ymax)``.
    :param segments: list of ``(x1, y1, x2, y2)`` pipeline vertex pairs, captured
        on the main thread.
    :param infra_geoms: list of detached ``QgsGeometry`` for the infrastructure
        (crossings) features; empty when no vector was selected.
    :returns: list of ``(Fc, Fs, Flu, Fci, N, Lcell)`` tuples, one per unique cell.
    """
    log("Step 1: Resampling all cost rasters to common resolution...")

    present = [(name, cost_specs[name]) for name in COST_NAMES if name in cost_specs]
    if not present:
        raise ValueError("At least one cost raster must be provided.")

    # Calculate common extent (intersection of all present extents).
    extents = [spec["extent"] for _, spec in present]
    xmin = max(e[0] for e in extents)
    xmax = min(e[1] for e in extents)
    ymin = max(e[2] for e in extents)
    ymax = min(e[3] for e in extents)
    if xmin >= xmax or ymin >= ymax:
        raise ValueError("No common extent found - cost rasters do not overlap!")

    # First present raster is the resolution / CRS reference.
    ref_spec = present[0][1]
    ref_resolution = ref_spec["res"]
    ref_crs_wkt = ref_spec["crs_wkt"]

    log(f"  Reference resolution: {ref_resolution:.2f}m from {ref_spec['name']}")

    # Resample present rasters only.
    temp_dir = tempfile.mkdtemp()
    target_extent = f"{xmin},{xmax},{ymin},{ymax}"
    resampled_data = {}

    for name, spec in present:
        resampled_path = os.path.join(temp_dir, f"_price_est_{name.replace(' ', '_')}.tif")

        resampled_output = resample_raster(
            spec["path"],
            resampled_path,
            ref_resolution,
            target_crs=ref_crs_wkt,
            target_extent=target_extent,
        )

        if resampled_output:
            ds = gdal.Open(resampled_output)
            data = ds.GetRasterBand(1).ReadAsArray().astype(np.float32)

            # Store metadata from first raster
            if not resampled_data:
                width = ds.RasterXSize
                height = ds.RasterYSize
                geotrans = ds.GetGeoTransform()
                resampled_data["_meta"] = {"width": width, "height": height, "geotrans": geotrans}

            resampled_data[name] = data
            ds = None
            log(f"  ✓ Resampled {name}")
        else:
            raise RuntimeError(f"Failed to resample {spec['name']}")

    # Get dimensions
    meta = resampled_data["_meta"]
    width, height = meta["width"], meta["height"]
    geotrans = meta["geotrans"]
    cell_width = abs(geotrans[1])
    cell_height = abs(geotrans[5])
    origin_x = geotrans[0]
    origin_y = geotrans[3]

    log(f"  Resampled grid: {width}x{height} cells, cell size: {cell_width:.2f}m x {cell_height:.2f}m")

    # Create arrays — missing rasters default to 1.0 (neutral)
    Flu = resampled_data.get("Land Use (Flu)", np.ones((height, width), dtype=np.float32))
    Fs = resampled_data.get("Slope (Fs)", np.ones((height, width), dtype=np.float32))
    Fc = resampled_data.get("Corridors (Fc)", np.ones((height, width), dtype=np.float32))
    Fci = resampled_data.get("Crossings (Fci)", np.ones((height, width), dtype=np.float32))

    for name in COST_NAMES:
        if name not in resampled_data:
            log(f"  ⚠️ {name}: Not selected — assuming constant 1.0 (neutral)")

    log("Step 2: Extracting pipeline segments and calculating cell intersections...")

    if not infra_geoms:
        log("  ⚠️ No infrastructure vector selected - N will be 1 for all cells (neutral, preserves Fci contribution)")
    else:
        log(f"  Loaded {len(infra_geoms)} infrastructure features for N calculation")

    # PRE-PASS: Quick count of total unique cells (fast, no heavy geometry operations)
    log("  Counting total unique cells...")
    unique_cells_set = set()
    for x1, y1, x2, y2 in segments:
        cells_touched = get_intersected_cells(
            x1, y1, x2, y2, origin_x, origin_y, cell_width, cell_height, width, height
        )
        unique_cells_set.update(cells_touched)

    total_unique_cells = len(unique_cells_set)
    log(f"  Found {total_unique_cells} unique cells to process")

    # Dictionary to accumulate data per cell: {(row, col): {'Fc': val, 'Fs': val, ..., 'L': total_length, 'N': count}}
    cell_data = {}

    total_segments = 0
    processed_cells = 0

    # Process pipeline segments
    for x1, y1, x2, y2 in segments:
        total_segments += 1

        # Create segment geometry
        segment_geom = QgsGeometry.fromPolylineXY([QgsPointXY(x1, y1), QgsPointXY(x2, y2)])

        # Get cells intersected by this segment
        cells_touched = get_intersected_cells(
            x1, y1, x2, y2, origin_x, origin_y, cell_width, cell_height, width, height
        )

        # For each cell touched by this segment
        for col, row in cells_touched:
            # Create cell polygon
            cell_x_min = origin_x + col * cell_width
            cell_x_max = cell_x_min + cell_width
            cell_y_max = origin_y - row * cell_height
            cell_y_min = cell_y_max - cell_height

            cell_rect = QgsRectangle(cell_x_min, cell_y_min, cell_x_max, cell_y_max)
            cell_polygon = QgsGeometry.fromRect(cell_rect)

            # Calculate intersection length (Lcell)
            intersection = segment_geom.intersection(cell_polygon)
            if intersection.isEmpty():
                continue

            length_in_cell = intersection.length()

            # Count infrastructure intersections within this cell (N)
            n_in_cell = 0
            for infra_geom in infra_geoms:
                # Check if infrastructure intersects both the segment AND the cell
                if segment_geom.intersects(infra_geom):
                    # Further check if intersection happens within this specific cell
                    infra_in_cell = infra_geom.intersection(cell_polygon)
                    if not infra_in_cell.isEmpty() and segment_geom.intersects(infra_in_cell):
                        n_in_cell += 1

            # Initialize cell data if first time
            cell_key = (row, col)
            is_new_cell = cell_key not in cell_data
            if is_new_cell:
                cell_data[cell_key] = {
                    "Fc": float(Fc[row, col]),
                    "Fs": float(Fs[row, col]),
                    "Flu": float(Flu[row, col]),
                    "Fci": float(Fci[row, col]),
                    "L": 0.0,
                    "N": 0,
                }
                processed_cells += 1

                # Log every single unique cell processed with total
                log(f"  Processing unique cell {processed_cells}/{total_unique_cells} (row={row}, col={col})")

            # Accumulate length and N
            cell_data[cell_key]["L"] += length_in_cell
            cell_data[cell_key]["N"] += n_in_cell

    log(f"  Processed {total_segments} segments across {len(cell_data)} unique cells")

    # Convert dictionary to list of tuples
    values = []
    for (_row, _col), data in cell_data.items():
        # If no infrastructure vector was provided, N defaults to 1 (preserves Fci contribution)
        # Cap N (same as LCP)
        n_capped = min(max(data["N"], 1 if not infra_geoms else 0), N_CAP)
        values.append((data["Fc"], data["Fs"], data["Flu"], data["Fci"], n_capped, data["L"]))

    log(f"  ✓ Extracted {len(values)} cell entries with total length: {sum(v[5] for v in values):.2f}m")

    # Cleanup temp files
    try:
        shutil.rmtree(temp_dir)
    except BaseException:
        pass

    return values


def extract_points(cost_paths, segments, crossings_geoms, log):
    """
    Fast extraction: iterate over vector segments (vertex-to-vertex), sample 5
    equally-spaced points along each segment on the original rasters and take the
    maximum value as the cost factor. Missing rasters default to 1.0 (neutral);
    missing infrastructure vector defaults N to 1.

    :param cost_paths: dict ``name -> path-or-None`` (``name`` one of :data:`COST_NAMES`).
    :param segments: list of ``(x1, y1, x2, y2)`` pipeline vertex pairs.
    :param crossings_geoms: list of detached ``QgsGeometry`` for the infrastructure
        (crossings) features; empty when no vector was selected.
    :returns: list of ``(Fc, Fs, Flu, Fci, N, Lseg)`` tuples, one per segment.
    """
    values = []

    # Build raster layers from paths on this (background) thread — NOT from the project.
    layers = {}
    for name in COST_NAMES:
        path = cost_paths.get(name)
        if not path:
            log(f"  ⚠️ {name}: Not selected — assuming constant 1.0 (neutral)")
            layers[name] = None
        else:
            layers[name] = QgsRasterLayer(path, name)

    corridors_layer = layers["Corridors (Fc)"]
    slope_layer = layers["Slope (Fs)"]
    land_use_layer = layers["Land Use (Flu)"]
    crossings_layer = layers["Crossings (Fci)"]

    for x1, y1, x2, y2 in segments:
        start = QgsPointXY(x1, y1)
        end = QgsPointXY(x2, y2)

        segment_geom = QgsGeometry.fromPolylineXY([start, end])
        num_intersections = 0
        for crossing_geom in crossings_geoms:
            if segment_geom.intersects(crossing_geom):
                num_intersections += 1
        # Default N to 1 if no infrastructure vector provided (preserves Fci contribution)
        if not crossings_geoms:
            num_intersections = 1

        cell_length = start.distance(end)
        sample_ratios = [0.0, 0.25, 0.5, 0.75, 1.0]
        corridors_vals, land_use_vals, slope_vals, crossings_vals = [], [], [], []

        for ratio in sample_ratios:
            x = x1 + (x2 - x1) * ratio
            y = y1 + (y2 - y1) * ratio
            point = QgsPointXY(x, y)

            Fc = get_raster_value_at_point(corridors_layer, point)
            Fs = get_raster_value_at_point(slope_layer, point)
            Flu = get_raster_value_at_point(land_use_layer, point)
            Fci = get_raster_value_at_point(crossings_layer, point)

            corridors_vals.append(Fc if Fc is not None else 1.0)
            slope_vals.append(Fs if Fs is not None else 1.0)
            land_use_vals.append(Flu if Flu is not None else 1.0)
            crossings_vals.append(Fci if Fci is not None else 1.0)

        values.append(
            (
                max(corridors_vals),
                max(slope_vals),
                max(land_use_vals),
                max(crossings_vals),
                num_intersections,
                cell_length,
            )
        )
    return values


def compute_capex(values, eng, log):
    """
    Compute the total pipeline investment cost (Itotal) from per-cell/segment cost
    factors and the engineering inputs.

    Diameter D is derived once (Darcy-Weisbach); the route is split into segments
    by the pressure budget (booster spacing), each segment cost (Ip) is the COMET
    summation, and a booster station (Ib) is inserted between consecutive segments.

    :param values: list of ``(Fc, Fs, Flu, Fci, N, Lcell)`` tuples.
    :param eng: dict with ``λ, M, p, Δp_Ltotal, total_pressure_drop,
        admissible_MPa_km, Bc, Beff, α, β``.
    :returns: ``{"I_total": float}``.
    """
    λ = eng["λ"]
    M = eng["M"]
    p = eng["p"]
    Δp_Ltotal = eng["Δp_Ltotal"]
    total_pressure_drop = eng["total_pressure_drop"]
    admissible_MPa_km = eng["admissible_MPa_km"]
    Bc = eng["Bc"]
    Beff = eng["Beff"]
    α = eng["α"]
    β = eng["β"]

    # Max segment length is derived from the pressure budget:
    # segment (km) = total pressure drop (MPa) / admissible pressure drop (MPa/km)
    max_segment_length = (total_pressure_drop / admissible_MPa_km) * 1000  # km → m
    log(
        f"Max segment length (booster spacing): {max_segment_length / 1000:.2f} km "
        f"(= {total_pressure_drop} MPa / {admissible_MPa_km} MPa/km)"
    )

    segment_costs = []
    booster_costs = []
    segment_index = 0

    current_segment_cells = []
    current_segment_length = 0

    # Calculate diameter D once for the entire pipeline using total length
    D = ((8 * λ * M**2) / (np.pi**2 * p * Δp_Ltotal)) ** (1 / 5)
    log(f"Pipeline Diameter (D): {D:.4f} m = {D * 1000:.2f} mm")
    log("--------------------------------------------------")

    # Final cell detected by index, not a float-sum comparison (see #15).
    last_index = len(values) - 1
    for i, (Fc, Fs, Flu, Fci, N, Lcell) in enumerate(values):
        current_segment_cells.append((Fc, Fs, Flu, Fci, N, Lcell))
        current_segment_length += Lcell

        segment_complete = current_segment_length >= max_segment_length
        final_segment = i == last_index

        if segment_complete or final_segment:
            L_segment = current_segment_length

            summation = sum(
                comet_cell_cost(fc_i, fs_i, flu_i, fci_i, n_i) * cl_i
                for fc_i, fs_i, flu_i, fci_i, n_i, cl_i in current_segment_cells
            )

            Ip = Bc * D * summation
            segment_costs.append(Ip)
            log(f"Segment {segment_index + 1}: Length = {L_segment:.2f} m, Cost (Ip) = {Ip:,.2f} €")

            if not final_segment:
                # Booster stations are placed at the end of each full segment.
                # Pressure drop over a full segment = Δp/L × segment length (= total_pressure_drop)
                ΔP_booster_segment = Δp_Ltotal * max_segment_length  # Pa (pressure drop over one segment)
                Sc_W = (M * ΔP_booster_segment) / (p * Beff)  # W (compressor power)
                Sc_MW = Sc_W / 1e6  # converted to MW
                Ib = (α * Sc_MW + β) * 1e6  # Convert M€ to €
                booster_costs.append(Ib)
                log(
                    f"Booster Station after {max_segment_length / 1000:.2f} km: "
                    f"ΔP_segment = {ΔP_booster_segment / 1e6:.2f} MPa, Sc = {Sc_MW:.2f} MW, Cost (Ib) = {Ib:,.2f} €"
                )

            current_segment_cells = []
            current_segment_length = 0
            segment_index += 1

    I_total = sum(segment_costs) + sum(booster_costs)
    log("--------------------------------------------------")
    log(f"Pipeline Diameter (D): {D:.4f} m = {D * 1000:.2f} mm")
    log(f"Calculated Total Pipeline Price (Itotal): {I_total:,.2f} €")
    log("--------------------------------------------------")

    return {"I_total": I_total}
