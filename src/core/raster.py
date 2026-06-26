"""Shared raster-processing helpers (domain layer, no Qt widgets)."""

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
