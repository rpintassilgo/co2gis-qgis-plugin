from typing import TYPE_CHECKING
from qgis import processing
from .path import get_plugin_output_path
import os
from qgis.core import ( QgsProcessingFeedback )

if TYPE_CHECKING:
    from ..dialog import Dialog
    from qgis.core import QgsMapLayer
    
os.environ["GRASS_VERBOSE"] = "3"  # Enable GRASS debugging

from osgeo import gdal
import numpy as np

from osgeo import gdal

from osgeo import gdal

# ------------ ------ ------------- ------ ---- GDAL --------- ------ ------------- ------ ------------- ------ ----
def resample_raster_by_resolution(dialog, input_raster_path, reference_raster_path, output_raster_path, resample_alg="bilinear"):
    """
    Resamples an input raster to match the resolution of a reference raster.
    """
    try:
        dialog.log_message("Starting raster resampling by resolution...")

        # Open reference raster
        ref_ds = gdal.Open(reference_raster_path)
        ref_gt = ref_ds.GetGeoTransform()
        ref_res_x, ref_res_y = abs(ref_gt[1]), abs(ref_gt[5])

        dialog.log_message(f"Reference resolution: {ref_res_x}, {ref_res_y}")

        # Resample the input raster to match the resolution of the reference raster
        gdal.Warp(
            output_raster_path,
            input_raster_path,
            format="GTiff",
            xRes=ref_res_x,
            yRes=ref_res_y,
            resampleAlg=resample_alg,
            dstSRS=ref_ds.GetProjection()
        )

        dialog.log_message(f"Resampled raster (by resolution) saved to: {output_raster_path}")
        return output_raster_path

    except Exception as e:
        dialog.log_message(f"Error during raster resampling by resolution: {str(e)}")
        return

def resample_raster_by_size(dialog, input_raster_path, reference_raster_path, output_raster_path, resample_alg="bilinear"):
    """
    Resamples an input raster to match the size and extent of a reference raster.
    """
    try:
        dialog.log_message("Starting raster resampling by size...")

        # Open reference raster
        ref_ds = gdal.Open(reference_raster_path)
        ref_gt = ref_ds.GetGeoTransform()
        ref_xmin = ref_gt[0]
        ref_ymax = ref_gt[3]
        ref_res_x = abs(ref_gt[1])
        ref_res_y = abs(ref_gt[5])
        ref_xmax = ref_xmin + ref_res_x * ref_ds.RasterXSize
        ref_ymin = ref_ymax - ref_res_y * ref_ds.RasterYSize
        output_bounds = [ref_xmin, ref_ymin, ref_xmax, ref_ymax]

        dialog.log_message(f"Reference bounds: {output_bounds}")

        # Resample the input raster to match the size and extent of the reference raster
        gdal.Warp(
            output_raster_path,
            input_raster_path,
            format="GTiff",
            outputBounds=output_bounds,
            width=ref_ds.RasterXSize,  # Match number of columns
            height=ref_ds.RasterYSize,  # Match number of rows
            resampleAlg=resample_alg,
            dstSRS=ref_ds.GetProjection()
        )

        dialog.log_message(f"Resampled raster (by size) saved to: {output_raster_path}")
        return output_raster_path

    except Exception as e:
        dialog.log_message(f"Error during raster resampling by size: {str(e)}")
        return


def combine_rasters_with_weights_gdal_api(dialog: 'Dialog', costs_raster_path, slope_raster_path, dem_weight, occupancy_weight, output_path):
    try:
        dialog.log_message("Combining land use costs raster and slope raster with weights using GDAL API...")

        # Open rasters
        costs_ds = gdal.Open(costs_raster_path)
        slope_ds = gdal.Open(slope_raster_path)
        
        #costs_nodata = costs_ds.GetRasterBand(1).GetNoDataValue() or -9999  # Default to -9999 if not set
        #slope_nodata = slope_ds.GetRasterBand(1).GetNoDataValue() or -9999
        
        #dialog.log_message("---- --- NO DATA ------- -----")
        #dialog.log_message(costs_nodata)
        #dialog.log_message(slope_nodata)
        #dialog.log_message("---- ----- ------ -------- ----")

        # Read raster bands as numpy arrays
        costs_band = costs_ds.GetRasterBand(1).ReadAsArray()
        slope_band = slope_ds.GetRasterBand(1).ReadAsArray()

        # Get geotransform and projection from one of the rasters
        geotransform = costs_ds.GetGeoTransform()
        projection = costs_ds.GetProjection()

        # Perform weighted raster calculation
        combined_array = (float(occupancy_weight) * costs_band) + (float(dem_weight) * slope_band)

        # Write the result to a new GeoTIFF
        driver = gdal.GetDriverByName("GTiff")
        out_ds = driver.Create(output_path, costs_ds.RasterXSize, costs_ds.RasterYSize, 1, gdal.GDT_Float32)
        out_ds.SetGeoTransform(geotransform)
        out_ds.SetProjection(projection)
        out_band = out_ds.GetRasterBand(1)
        out_band.WriteArray(combined_array)
        out_band.SetNoDataValue(-9999)  # Replace with appropriate NoData value

        # Cleanup
        costs_ds = None
        slope_ds = None
        out_ds = None

        dialog.log_message(f"Combined raster created with gdal pyAPI at: {output_path}")
        return output_path

    except Exception as e:
        dialog.log_message(f"Error combining rasters using GDAL API: {str(e)}")
        return

## --------- ------ ---- --------- ------ ---- --------- ------ ---- --------- ------ ---- --------- ------ ----
def combine_rasters_with_qgis_raster_calculator(input_raster1, input_raster2, weight1, weight2, output_raster_path):
    """
    Combine two rasters with weights without preprocessing using QGIS Raster Calculator.
    """
    try:
        feedback = QgsProcessingFeedback()
        formula = f"({weight1} * A) + ({weight2} * B)"

        params = {
            'EXPRESSION': formula,
            'LAYERS': [input_raster1, input_raster2],
            'CELLSIZE': 0,  # Automatically determines resolution
            'EXTENT': None,  # Automatically uses the union of extents
            'OUTPUT': output_raster_path
        }

        processing.run("qgis:rastercalculator", params, feedback)
        print(f"Combined raster saved at: {output_raster_path}")
        return  #output_raster_path

    except Exception as e:
        print(f"Error combining rasters: {str(e)}")
        return


def combine_rasters_with_weights(dialog: 'Dialog', costs_raster: 'QgsMapLayer', slope_raster: 'QgsMapLayer', dem_weight, occupancy_weight, output_path):
    try:
        dialog.log_message("Combining land use costs raster and slope raster with weights...")

        # build the raster calculator expression
        expression = f"({occupancy_weight} * \"{costs_raster.name()}@1\") + ({dem_weight} * \"{slope_raster.name()}@1\")"
        dialog.log_message(expression)
        
        # todo: theres that situation that needed to be fixed later, the resolution differences
        params = {
            'EXPRESSION': expression,
            'LAYERS': [costs_raster, slope_raster],
            'CELLSIZE': 0,
            'EXTENT': None,
            'CRS': None,  # if none, it uses the CRS of input rasters
            'OUTPUT': output_path
        }

        result = processing.run("qgis:rastercalculator", params)

        dialog.log_message(f"Combined raster created at: {result['OUTPUT']}")
        return result['OUTPUT']

    except Exception as e:
        dialog.log_message(f"Error combining rasters: {str(e)}")
        raise RuntimeError(f"Failed to combine rasters: {str(e)}")


def clip_raster_to_vector(dialog: 'Dialog', raster_path, vector_layer, output_raster_path, buffer=0):
    """
    Clips a raster based on the bounding box of a vector layer.

    Args:
        dialog: Logger object to display messages.
        raster_path (str): Path to the raster to be clipped.
        vector_layer (QgsVectorLayer): A vector layer containing the points.
        output_raster_path (str): Path to save the clipped raster.
        buffer (float): Optional buffer to add around the bounding box.
    """
    try:
        # Calculate the bounding box of the vector layer
        extent = vector_layer.extent()
        xmin = extent.xMinimum() - buffer
        ymin = extent.yMinimum() - buffer
        xmax = extent.xMaximum() + buffer
        ymax = extent.yMaximum() + buffer

        dialog.log_message(f"Clipping raster with bounding box: [{xmin}, {ymin}, {xmax}, {ymax}]")

        # Clip the raster using gdal.Warp
        gdal.Warp(
            output_raster_path,
            raster_path,
            format="GTiff",
            outputBounds=[xmin, ymin, xmax, ymax],
            cropToCutline=True
        )

        dialog.log_message(f"Clipped raster saved to: {output_raster_path}")
        return output_raster_path

    except Exception as e:
        dialog.log_message(f"Error clipping raster: {str(e)}")
        return
    
def run_r_cost(land_use_layer, points_layer):
    output_path = get_plugin_output_path("r_cost_output.tif")
    
    params_r_cost = {
        'input': land_use_layer,
        'start_points': points_layer,
        'output': output_path,
        'memory': 4000 # allocate 2GB
    }
    
    try:
        result = processing.run("grass7:r.cost", params_r_cost)

        if 'output' not in result or not result['output']:
            print("RESULTDO DO R.COST INVALIDO")

        return result
    except Exception as e:
        raise RuntimeError(f"Error running r.cost: {str(e)}")