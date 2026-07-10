"""Shared raster-processing helpers (domain layer, no Qt widgets)."""

import os

import numpy as np
from osgeo import gdal
from qgis import processing

# Standard GDAL creation options used for every resampled output in the plugin.
RESAMPLE_EXTRA = "-co COMPRESS=LZW -co BIGTIFF=YES"


def resample_raster(
    input_layer,
    output_path,
    target_resolution,
    *,
    resampling=0,
    source_crs=None,
    target_crs=None,
    target_extent=None,
    nodata=None,
    extra=RESAMPLE_EXTRA,
):
    """Run ``gdal:warpreproject`` with the plugin's standard options.

    Wraps the warpreproject parameter dict that was duplicated across the LCP,
    Price Estimation, Aux and Corridors tabs. CRS / extent arguments are only
    added to the parameters when provided, so a plain resample (Aux) and a
    reproject-to-reference resample (LCP/Price/Corridors) share one code path.

    :param input_layer: source raster (QgsRasterLayer or path).
    :param output_path: destination ``.tif`` path.
    :param target_resolution: output pixel size in target CRS units.
    :param resampling: GDAL resampling code (0=nearest, 1=bilinear, ...).
    :param source_crs / target_crs: optional CRS objects or WKT/proj strings.
    :param target_extent: optional ``"xmin,xmax,ymin,ymax"`` string.
    :param nodata: optional output NoData value.
    :returns: the OUTPUT path produced by the algorithm, or ``None`` on failure.
    """
    params = {
        "INPUT": input_layer,
        "RESAMPLING": resampling,
        "NODATA": nodata,
        "TARGET_RESOLUTION": target_resolution,
        "OUTPUT": output_path,
        "EXTRA": extra,
    }
    if source_crs is not None:
        params["SOURCE_CRS"] = source_crs
    if target_crs is not None:
        params["TARGET_CRS"] = target_crs
    if target_extent is not None:
        params["TARGET_EXTENT"] = target_extent

    result = processing.run("gdal:warpreproject", params)
    return result.get("OUTPUT") if result else None


def resample_present_to_common_grid(present, target_crs_wkt, temp_dir, file_prefix, log):
    """Resample the *present* cost rasters onto one shared grid and read them into arrays.

    The grid is the intersection of every present raster's extent, at the first present
    raster's resolution, reprojected to ``target_crs_wkt``. This is the scaffolding shared
    by the routing surface (:func:`~src.core.lcp.combine_rasters_with_comet_formula`) and
    the CAPEX sampler (:func:`~src.core.capex._resample_grid`) — keeping it in one place
    stops the two from drifting onto different grids.

    :param present: non-empty ``[(name, spec), ...]`` where each ``spec`` carries ``path``,
        ``extent`` ``(xmin, xmax, ymin, ymax)``, ``res`` and ``name``.
    :param target_crs_wkt: WKT the output grid is reprojected to.
    :param temp_dir: existing directory the intermediate ``.tif`` files are written to; the
        caller owns it and is responsible for removing it.
    :param file_prefix: filename prefix for each intermediate raster.
    :returns: ``{name: float32 array}`` for every present raster, plus a ``"_meta"`` entry
        ``{"width", "height", "geotrans", "proj"}`` describing the common grid.
    """
    # Common extent = intersection of all present extents.
    extents = [spec["extent"] for _, spec in present]
    xmin = max(e[0] for e in extents)
    xmax = min(e[1] for e in extents)
    ymin = max(e[2] for e in extents)
    ymax = min(e[3] for e in extents)
    if xmin >= xmax or ymin >= ymax:
        raise ValueError("No common extent found - rasters do not overlap!")

    # First present raster is the resolution reference.
    ref_spec = present[0][1]
    ref_resolution = ref_spec["res"]
    log(f"  Reference resolution: {ref_resolution:.2f}m from {ref_spec['name']}")

    target_extent = f"{xmin},{xmax},{ymin},{ymax}"
    resampled = {}
    for name, spec in present:
        resampled_path = os.path.join(temp_dir, f"{file_prefix}{name.replace(' ', '_')}.tif")
        out = resample_raster(
            spec["path"], resampled_path, ref_resolution, target_crs=target_crs_wkt, target_extent=target_extent
        )
        if not out:
            raise RuntimeError(f"Failed to resample {spec['name']}")

        ds = gdal.Open(out)
        if ds is None:
            raise RuntimeError(f"Failed to open resampled raster for {name}")
        data = ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
        if "_meta" not in resampled:
            resampled["_meta"] = {
                "width": ds.RasterXSize,
                "height": ds.RasterYSize,
                "geotrans": ds.GetGeoTransform(),
                "proj": ds.GetProjection(),
            }
            log(f"  Target grid: {ds.RasterXSize}x{ds.RasterYSize} pixels")
        resampled[name] = data
        ds = None

        # Free disk during the loop; the caller's temp_dir cleanup is the backstop.
        try:
            os.remove(out)
        except OSError:
            pass

        log(f"  ✓ Resampled {name}")

    return resampled


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
