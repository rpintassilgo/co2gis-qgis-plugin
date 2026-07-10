"""CAPEX domain logic: cost-factor sampling along the pipeline + the COMET CAPEX math.

Pure domain — no Qt widgets, no dialog, no ``QgsProject`` access, no live-layer
iteration. Inputs are plain values / source paths / detached geometry captured on
the main thread; rasters are rebuilt from their paths on the background thread when
needed (the 3-phase task contract, #2). Progress is reported through a ``log(msg)``
callback (bridged to the thread-safe ``dialog.log_message``).

Stays consistent with the routing surface (``core.lcp``) by sharing
:func:`~src.core.comet.comet_cell_cost` and :data:`~src.constants.comet.N_CAP`.

Two CAPEX entry points share the same physics helpers (``_diameter`` / ``_booster_cost`` /
``_walk_pressure_segments``): :func:`compute_capex` costs a single pipeline (one diameter),
and :func:`compute_network_capex` costs a network — each segment sized for its own flow, plus
a junction booster where flows merge.
"""

import os
import shutil
import tempfile

import numpy as np
from osgeo import gdal
from qgis.core import QgsGeometry, QgsPointXY, QgsRaster, QgsRasterLayer, QgsRectangle

from ..constants.comet import N_CAP
from .comet import comet_cell_cost
from .networks.graph import cluster_edges
from .raster import resample_raster

# Canonical COMET cost-factor slots, in formula order. ``extract_cells`` /
# ``extract_points`` key their inputs by these names.
COST_NAMES = ["Land Use (Flu)", "Slope (Fs)", "Corridors (Fc)", "Crossings (Fci)"]

# Continuous operation: 1 Mt/yr spread over a full year in seconds (8766 h).
SECONDS_PER_YEAR = 31_557_600.0


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


def _resample_grid(cost_specs, log):
    """Resample the present cost rasters to a common grid (intersection extent, first
    raster's resolution/CRS). Returns ``(grid, temp_dir)`` — the caller removes ``temp_dir``.

    ``grid`` holds the resampled ``Flu/Fs/Fc/Fci`` arrays (missing → constant 1.0) and the
    grid geometry (``width, height, cell_width, cell_height, origin_x, origin_y``). Resampling
    once lets a whole network reuse one grid (:func:`_walk_cells` per segment).
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

    temp_dir = tempfile.mkdtemp()
    target_extent = f"{xmin},{xmax},{ymin},{ymax}"
    resampled_data = {}

    for name, spec in present:
        resampled_path = os.path.join(temp_dir, f"_price_est_{name.replace(' ', '_')}.tif")
        resampled_output = resample_raster(
            spec["path"], resampled_path, ref_resolution, target_crs=ref_crs_wkt, target_extent=target_extent
        )
        if resampled_output:
            ds = gdal.Open(resampled_output)
            data = ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
            if not resampled_data:
                resampled_data["_meta"] = {
                    "width": ds.RasterXSize,
                    "height": ds.RasterYSize,
                    "geotrans": ds.GetGeoTransform(),
                }
            resampled_data[name] = data
            ds = None
            log(f"  ✓ Resampled {name}")
        else:
            raise RuntimeError(f"Failed to resample {spec['name']}")

    meta = resampled_data["_meta"]
    width, height, geotrans = meta["width"], meta["height"], meta["geotrans"]

    # Missing rasters default to 1.0 (neutral).
    Flu = resampled_data.get("Land Use (Flu)", np.ones((height, width), dtype=np.float32))
    Fs = resampled_data.get("Slope (Fs)", np.ones((height, width), dtype=np.float32))
    Fc = resampled_data.get("Corridors (Fc)", np.ones((height, width), dtype=np.float32))
    Fci = resampled_data.get("Crossings (Fci)", np.ones((height, width), dtype=np.float32))
    for name in COST_NAMES:
        if name not in resampled_data:
            log(f"  ⚠️ {name}: Not selected — assuming constant 1.0 (neutral)")

    grid = {
        "Flu": Flu,
        "Fs": Fs,
        "Fc": Fc,
        "Fci": Fci,
        "width": width,
        "height": height,
        "cell_width": abs(geotrans[1]),
        "cell_height": abs(geotrans[5]),
        "origin_x": geotrans[0],
        "origin_y": geotrans[3],
    }
    log(f"  Resampled grid: {width}x{height} cells, cell size: {grid['cell_width']:.2f}m x {grid['cell_height']:.2f}m")
    return grid, temp_dir


def _walk_cells(grid, segments, infra_geoms, log):
    """Walk a pipeline over a resampled ``grid`` (from :func:`_resample_grid`) cell by cell,
    computing the exact length within each cell (Lcell) and counting infrastructure crossings (N).

    :returns: list of ``(Fc, Fs, Flu, Fci, N, Lcell)`` tuples, one per unique cell.
    """
    Flu, Fs, Fc, Fci = grid["Flu"], grid["Fs"], grid["Fc"], grid["Fci"]
    width, height = grid["width"], grid["height"]
    cell_width, cell_height = grid["cell_width"], grid["cell_height"]
    origin_x, origin_y = grid["origin_x"], grid["origin_y"]

    log("Step 2: Extracting pipeline segments and calculating cell intersections...")

    if not infra_geoms:
        log("  ⚠️ No infrastructure vector selected - N will be 1 for all cells (neutral, preserves Fci contribution)")
    else:
        log(f"  Loaded {len(infra_geoms)} infrastructure features for N calculation")

    # PRE-PASS: Quick count of total unique cells (fast, no heavy geometry operations)
    unique_cells_set = set()
    for x1, y1, x2, y2 in segments:
        unique_cells_set.update(
            get_intersected_cells(x1, y1, x2, y2, origin_x, origin_y, cell_width, cell_height, width, height)
        )
    total_unique_cells = len(unique_cells_set)
    log(f"  Found {total_unique_cells} unique cells to process")

    # Dictionary to accumulate data per cell: {(row, col): {Fc, Fs, Flu, Fci, L, N}}
    cell_data = {}
    total_segments = 0
    processed_cells = 0

    # Throttle progress logging to ~every 5% of unique cells (at least every cell for short routes).
    log_interval = max(1, total_unique_cells // 20)

    for x1, y1, x2, y2 in segments:
        total_segments += 1
        segment_geom = QgsGeometry.fromPolylineXY([QgsPointXY(x1, y1), QgsPointXY(x2, y2)])
        cells_touched = get_intersected_cells(
            x1, y1, x2, y2, origin_x, origin_y, cell_width, cell_height, width, height
        )

        for col, row in cells_touched:
            cell_x_min = origin_x + col * cell_width
            cell_x_max = cell_x_min + cell_width
            cell_y_max = origin_y - row * cell_height
            cell_y_min = cell_y_max - cell_height

            cell_rect = QgsRectangle(cell_x_min, cell_y_min, cell_x_max, cell_y_max)
            cell_polygon = QgsGeometry.fromRect(cell_rect)

            intersection = segment_geom.intersection(cell_polygon)
            if intersection.isEmpty():
                continue

            length_in_cell = intersection.length()

            # Count infrastructure intersections within this cell (N)
            n_in_cell = 0
            for infra_geom in infra_geoms:
                if segment_geom.intersects(infra_geom):
                    infra_in_cell = infra_geom.intersection(cell_polygon)
                    if not infra_in_cell.isEmpty() and segment_geom.intersects(infra_in_cell):
                        n_in_cell += 1

            cell_key = (row, col)
            if cell_key not in cell_data:
                cell_data[cell_key] = {
                    "Fc": float(Fc[row, col]),
                    "Fs": float(Fs[row, col]),
                    "Flu": float(Flu[row, col]),
                    "Fci": float(Fci[row, col]),
                    "L": 0.0,
                    "N": 0,
                }
                processed_cells += 1
                if processed_cells % log_interval == 0 or processed_cells == total_unique_cells:
                    pct = processed_cells / total_unique_cells * 100
                    log(f"  Processing cells: {processed_cells}/{total_unique_cells} ({pct:.0f}%)")

            cell_data[cell_key]["L"] += length_in_cell
            cell_data[cell_key]["N"] += n_in_cell

    log(f"  Processed {total_segments} segments across {len(cell_data)} unique cells")

    # Convert dictionary to list of tuples. If no infrastructure vector was provided, N defaults
    # to 1 (preserves Fci contribution); cap N (same as LCP).
    values = []
    for (_row, _col), data in cell_data.items():
        n_capped = min(max(data["N"], 1 if not infra_geoms else 0), N_CAP)
        values.append((data["Fc"], data["Fs"], data["Flu"], data["Fci"], n_capped, data["L"]))

    log(f"  ✓ Extracted {len(values)} cell entries with total length: {sum(v[5] for v in values):.2f}m")
    return values


def extract_cells(cost_specs, segments, infra_geoms, log):
    """Precise extraction for a single route: resample the present cost rasters to a common
    grid (:func:`_resample_grid`), then walk the pipeline cell by cell (:func:`_walk_cells`).

    :param cost_specs: dict ``name -> {"path", "crs_wkt", "extent", "res", "name"}`` for the
        PRESENT cost rasters only (``name`` one of :data:`COST_NAMES`).
    :param segments: list of ``(x1, y1, x2, y2)`` pipeline vertex pairs (main thread).
    :param infra_geoms: detached ``QgsGeometry`` list for the crossings features (may be empty).
    :returns: list of ``(Fc, Fs, Flu, Fci, N, Lcell)`` tuples, one per unique cell.
    """
    grid, temp_dir = _resample_grid(cost_specs, log)
    try:
        return _walk_cells(grid, segments, infra_geoms, log)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


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

    if not crossings_geoms:
        log(
            "  ⚠️ No infrastructure vector selected - N will be 1 for all route sections "
            "(neutral, preserves Fci contribution)"
        )
    else:
        log(f"  Loaded {len(crossings_geoms)} infrastructure features for N calculation")

    # Each item is one vertex-to-vertex section of the route polyline ("route section" to avoid
    # clashing with the pressure-budget "segments" between boosters that compute_capex logs later).
    total_sections = len(segments)
    log(f"  Sampling {total_sections} route sections (5 points each)...")
    # Throttle progress to ~every 5% (at least every section for short routes), mirroring extract_cells.
    log_interval = max(1, total_sections // 20)

    for i, (x1, y1, x2, y2) in enumerate(segments, start=1):
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

        # Report progress on a throttled cadence (every ~5%) plus a final 100% line.
        if i % log_interval == 0 or i == total_sections:
            pct = i / total_sections * 100
            log(f"  Processing route sections: {i}/{total_sections} ({pct:.0f}%)")

    return values


def extract_network_values(edges, cost_specs, cost_paths, infra_geoms, mode, log):
    """Sample the cost factors along each network edge's segments, filling ``edge["values"]``.

    Precise resamples the common grid ONCE (:func:`_resample_grid`) and walks every edge over it;
    fast samples points per edge (:func:`extract_points`). Mutates and returns ``edges``.

    :param edges: list of ``{"flow", "junction", "segments": [(x1,y1,x2,y2)…]}``.
    :param mode: ``"precise"`` or ``"fast"``.
    """
    if mode == "precise":
        grid, temp_dir = _resample_grid(cost_specs, log)
        try:
            for i, edge in enumerate(edges, start=1):
                log(f"Segment {i}/{len(edges)} (flow {edge['flow']:g} Mt/yr): sampling cells...")
                edge["values"] = _walk_cells(grid, edge["segments"], infra_geoms, log)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    else:
        for i, edge in enumerate(edges, start=1):
            log(f"Segment {i}/{len(edges)} (flow {edge['flow']:g} Mt/yr): sampling points...")
            edge["values"] = extract_points(cost_paths, edge["segments"], infra_geoms, log)
    return edges


def mt_yr_to_kg_s(flow_mt_yr):
    """Continuous mass flow: Mt/yr → kg/s (1 Mt/yr ≈ 31.69 kg/s, 10⁹ kg over 8766 h)."""
    return flow_mt_yr * 1e9 / SECONDS_PER_YEAR


def _diameter(M, eng):
    """Darcy-Weisbach inner pipeline diameter (m) for mass flow ``M`` (kg/s)."""
    return ((8 * eng["λ"] * M**2) / (np.pi**2 * eng["p"] * eng["Δp_Ltotal"])) ** (1 / 5)


def _booster_cost(M, eng):
    """Booster station cost Ib (€) for flow ``M`` (kg/s), recovering one segment's Δp.

    One rule for spacing boosters and junction boosters: Sc = M·Δp/(ρ·Beff) with
    Δp = ``total_pressure_drop`` (MPa → Pa); Ib = (α·Sc[MW] + β)·1e6.
    """
    ΔP = eng["total_pressure_drop"] * 1e6  # MPa → Pa
    Sc_MW = (M * ΔP) / (eng["p"] * eng["Beff"]) / 1e6
    return (eng["α"] * Sc_MW + eng["β"]) * 1e6


def _walk_pressure_segments(values, D, M, eng):
    """Split ``values`` (per-cell COMET factors + Lcell) into pressure-budget **segments**.

    Each segment spans up to ``max_segment_length`` (the pressure budget,
    ``total_pressure_drop / admissible_MPa_km``); a spacing booster sits between consecutive
    segments (the final, possibly short, segment gets none). No logging — the callers format
    the output (single vs network).

    :returns: ``(segments, boosters)`` — ``segments`` a list of ``(length_m, Ip)`` and
        ``boosters`` a list of Ib (€), one per gap.
    """
    Bc = eng["Bc"]
    max_segment_length = (eng["total_pressure_drop"] / eng["admissible_MPa_km"]) * 1000  # km → m

    segments = []
    boosters = []
    current_cells = []
    current_length = 0.0
    last_index = len(values) - 1

    # Final cell detected by index, not a float-sum comparison (see #15).
    for i, (Fc, Fs, Flu, Fci, N, Lcell) in enumerate(values):
        current_cells.append((Fc, Fs, Flu, Fci, N, Lcell))
        current_length += Lcell

        if current_length >= max_segment_length or i == last_index:
            summation = sum(
                comet_cell_cost(fc_i, fs_i, flu_i, fci_i, n_i) * cl_i
                for fc_i, fs_i, flu_i, fci_i, n_i, cl_i in current_cells
            )
            segments.append((current_length, Bc * D * summation))
            if i != last_index:
                boosters.append(_booster_cost(M, eng))
            current_cells = []
            current_length = 0.0

    return segments, boosters


def compute_capex(values, eng, log):
    """
    Compute the total pipeline investment cost (Itotal) for a single pipeline.

    Diameter D is derived once (Darcy-Weisbach) from ``eng["M"]``; the route is split into
    **segments** by the pressure budget (booster spacing), each segment cost (Ip) is the COMET
    summation, and a booster station (Ib) is inserted between consecutive segments.

    :param values: list of ``(Fc, Fs, Flu, Fci, N, Lcell)`` tuples.
    :param eng: dict with ``λ, M, p, Δp_Ltotal, total_pressure_drop, admissible_MPa_km,
        Bc, Beff, α, β``.
    :returns: ``{"I_total": float}``.
    """
    M = eng["M"]
    D = _diameter(M, eng)
    max_segment_length = (eng["total_pressure_drop"] / eng["admissible_MPa_km"]) * 1000

    segments, boosters = _walk_pressure_segments(values, D, M, eng)
    pipe_cost = sum(Ip for _, Ip in segments)
    spacing_cost = sum(boosters)
    I_total = pipe_cost + spacing_cost

    # Same table styling as the network log (monospace): a header, one row per pressure segment,
    # boosters marked with ⊕, and the totals footer.
    log(
        f"Single pipeline CAPEX — M {M:g} kg/s → D {D * 1000:.1f} mm · "
        f"booster spacing {max_segment_length / 1000:.0f} km "
        f"(= {eng['total_pressure_drop']:g} MPa ÷ {eng['admissible_MPa_km']:g} MPa/km) · {len(segments)} segment(s)"
    )
    log("--------------------------------------------------")
    for idx, (length, Ip) in enumerate(segments):
        log(f"{idx + 1:>4}  {length / 1000:>8.2f} km   Ip {Ip / 1e6:>8.2f} M€")
        if idx < len(boosters):
            log(f"      ⊕ spacing booster: Ib {boosters[idx] / 1e6:.2f} M€")
    log("--------------------------------------------------")
    if spacing_cost:
        log(f"Total: pipe {pipe_cost:,.0f} € + spacing boosters {spacing_cost:,.0f} €")
    log(f"Calculated Total Pipeline Price (Itotal): {I_total:,.2f} €")
    log("--------------------------------------------------")

    return {"I_total": I_total}


def compute_network_capex(edges, eng, log):
    """
    Compute the total investment cost (Itotal) for a pipeline NETWORK.

    Each **pipe** (a network edge — a spur or trunk) is sized for ITS OWN flow: M from the pipe's
    flow (Mt/yr → kg/s), a diameter D from that M, then the pipe is split into pressure-budget
    **segments** + spacing boosters (exactly like a single pipeline). Where flows merge
    (``junction``) a full junction booster is added, sized with the merged downstream M (option A —
    same rule as a spacing booster). ``eng["M"]`` is ignored.

    Terminology matches single mode: a *pipe* is the network edge; a *segment* is a pressure piece
    within it (only >1 when a pipe is longer than the booster spacing).

    :param edges: list of ``{"flow": Mt/yr, "junction": bool, "values": [(Fc,Fs,Flu,Fci,N,Lcell)…]}``.
    :param eng: as in :func:`compute_capex`.
    :returns: ``{"I_total", "n_junction_boosters"}``.
    """
    max_segment_length = (eng["total_pressure_drop"] / eng["admissible_MPa_km"]) * 1000

    # Pass 1 — cost every pipe (network edge) for its own flow; stash the results on the edge.
    total_pipe = 0.0
    total_spacing = 0.0
    total_junction = 0.0
    n_junction = 0
    for edge in edges:
        M = mt_yr_to_kg_s(edge["flow"])
        D = _diameter(M, eng)
        segments, boosters = _walk_pressure_segments(edge["values"], D, M, eng)
        edge["_D"] = D
        edge["_length"] = sum(seg_len for seg_len, _ in segments)
        edge["_ip"] = sum(Ip for _, Ip in segments)
        edge["_segments"] = segments
        edge["_spacing"] = boosters
        edge["_junction_booster"] = _booster_cost(M, eng) if edge.get("junction") else 0.0
        total_pipe += edge["_ip"]
        total_spacing += sum(boosters)
        if edge.get("junction"):
            total_junction += edge["_junction_booster"]
            n_junction += 1
    I_total = total_pipe + total_spacing + total_junction

    # Pass 2 — log as a tree: cluster the pipes (by shared endpoints) and, per junction, show which
    # feeder pipes merge into which trunk (by fid, so the log cross-references the map).
    log(
        f"Network CAPEX — {len(edges)} pipe(s), {n_junction} junction(s) · "
        f"booster spacing {max_segment_length / 1000:.0f} km "
        f"(= {eng['total_pressure_drop']:g} MPa ÷ {eng['admissible_MPa_km']:g} MPa/km)"
    )
    log("--------------------------------------------------")
    clusters = cluster_edges(edges)
    multi = len(clusters) > 1
    for ci, cluster in enumerate(clusters, start=1):
        indent = ""
        if multi:
            log(f"Cluster {ci}:")
            indent = "  "
        # "trunk" = the highest-flow pipe(s) of the cluster, "spur" = a feeder — a topology role read
        # from the flow, so it's correct for both methods (the MILP flags the source→source feeder as a
        # junction, not the trunk, so the flag itself can't label the role).
        max_flow = max((e["flow"] for e in cluster["edges"]), default=0.0)
        for e in cluster["edges"]:
            role = "trunk" if e["flow"] >= max_flow - 1e-9 else "spur"
            log(
                f"{indent}{str(e.get('fid', '?')):>4}  {role:<5}  {e['flow']:>4.1f} Mt/yr  "
                f"{e['_D'] * 1000:>4.0f} mm  {e['_length'] / 1000:>6.2f} km  Ip {e['_ip'] / 1e6:>7.2f} M€"
            )
            if len(e["_segments"]) > 1:  # a pipe longer than the booster spacing splits into segments
                for s, (seg_len, Ip) in enumerate(e["_segments"]):
                    log(f"{indent}        segment {s + 1}: {seg_len / 1000:.2f} km, Ip {Ip / 1e6:.2f} M€")
                    if s < len(e["_spacing"]):
                        log(f"{indent}        + spacing booster: Ib {e['_spacing'][s] / 1e6:.2f} M€")
        for j in cluster["junctions"]:
            pipe, feeders = j["trunk"], j["feeders"]
            fid, flow, ib = pipe.get("fid", "?"), pipe["flow"], pipe["_junction_booster"] / 1e6
            # Where the heuristic knows which pipes merge, name them ("fed by …"); the MILP puts the
            # booster on a hub-to-hub link with no separate feeders, so just name the pipe.
            fed = " + ".join(f"fid {f.get('fid', '?')} ({f['flow']:g})" for f in feeders)
            detail = f": fed by {fed}" if fed else ""
            log(f"{indent}  ⊕ junction booster on fid {fid} ({flow:g} Mt/yr){detail}  ·  Ib {ib:.2f} M€")

    log("--------------------------------------------------")
    log(
        f"Network: pipe {total_pipe:,.0f} € + spacing boosters {total_spacing:,.0f} € "
        f"+ {n_junction} junction booster(s) {total_junction:,.0f} €"
    )
    log(f"Calculated Total Network Price (Itotal): {I_total:,.2f} €")
    log("--------------------------------------------------")

    return {"I_total": I_total, "n_junction_boosters": n_junction}
