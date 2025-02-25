from typing import TYPE_CHECKING
from qgis import processing
from .path import get_plugin_output_path
import os
from qgis.core import ( QgsProcessingFeedback )

if TYPE_CHECKING:
    from ..complete_dialog import Dialog
    from qgis.core import QgsMapLayer, QgsVectorLayer
    
os.environ["GRASS_VERBOSE"] = "3"  # Enable GRASS debugging
#os.environ['GRASS_TEMP'] = "/Volumes/rodrigo/ficheiros/temp"

from osgeo import gdal

def combine_rasters_with_qgis_raster_calculator(input_raster1, input_raster2, weight1, weight2, output_raster_path):
    """
    Combine two rasters with weights without preprocessing using QGIS Raster Calculator.
    """
    try:
        feedback = QgsProcessingFeedback()
        formula = f"({weight1} * \"{input_raster1}@1\") + ({weight2} * \"{input_raster2}@1\")"

        params = {
            'EXPRESSION': formula,
            'LAYERS': [input_raster1, input_raster2],
            'CELLSIZE': 0,  # Automatically determines resolution
            'EXTENT': None,  # Automatically uses the union of extents
            'OUTPUT': output_raster_path
        }

        processing.run("qgis:rastercalculator", params, feedback=feedback)
        print(f"Combined raster saved at: {output_raster_path}")
        return

    except Exception as e:
        raise e


def clip_raster_to_vector(raster_path, vector_layer, output_raster_path, buffer=1000):
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

        # Clip the raster using gdal.Warp
        gdal.Warp(
            output_raster_path,
            raster_path,
            format="GTiff",
            outputBounds=[xmin, ymin, xmax, ymax],
            cropToCutline=True
        )
        return output_raster_path

    except Exception as e:
        raise e
    
def run_r_cost(land_use_layer, points_layer, cost_output_path, direction_output_path):
    try:
        vector_layer: QgsVectorLayer = points_layer
        
        # Extract start point coordinates from vector layer
        start_coordinates = []
        for feature in vector_layer.getFeatures():
            geometry = feature.geometry()
            if geometry.isMultipart():
                point = geometry.asMultiPoint()[0]
            else:
                point = geometry.asPoint()
            start_coordinates.append(f"{point.x()},{point.y()}")

        if len(start_coordinates) < 1:
            raise RuntimeError("At least one start point is required for r.cost.")

        start_coord = start_coordinates[0]  # Use first point as start

        # Define r.cost parameters
        params_r_cost = {
            'input': land_use_layer,
            'start_coordinates': start_coord,  # Start point
            'output': cost_output_path,  # Cumulative cost raster
            'outdir': direction_output_path,  # Movement directions raster
            'memory': 2000,
            'max_cost': None,
            'GRASS_REGION_PARAMETER': None,  
            'flags': ''  # No color table (c talvez de prevent do add color table ver depois)
        }
    
        result = processing.run("grass7:r.cost", params_r_cost)

        if not os.path.exists(cost_output_path) or not os.path.exists(direction_output_path):
            raise RuntimeError("r.cost failed to generate outputs.")
        
        return {
            'cost_raster': cost_output_path,  # This is the cumulative cost
            'direction_raster': direction_output_path  # This is the movement direction
        }

    except Exception as e:
        raise RuntimeError(f"Error in r.cost: {str(e)}")