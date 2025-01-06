from typing import TYPE_CHECKING
from qgis import processing
from .path import get_plugin_output_path
import os
from qgis.core import ( QgsProcessingFeedback )

if TYPE_CHECKING:
    from ..dialog import Dialog
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

        processing.run("qgis:rastercalculator", params, feedback)
        print(f"Combined raster saved at: {output_raster_path}")
        return  #output_raster_path

    except Exception as e:
        print(f"Error combining rasters: {str(e)}")
        return


def clip_raster_to_vector(dialog: 'Dialog', raster_path, vector_layer, output_raster_path, buffer=1000):
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
    
def run_r_cost(dialog: 'Dialog', land_use_layer, points_layer):
    cost_output_path = get_plugin_output_path("r_cost_output.tif")
    direction_output_path = get_plugin_output_path("direction_output.tif")  # Path for direction raster
    
    try:
        vector_layer: QgsVectorLayer = points_layer
        
        # Get the coordinates of the points in the points_layer
        start_coordinates = []
        for feature in vector_layer.getFeatures():
            geometry = feature.geometry()
            if geometry.isMultipart():
                point = geometry.asMultiPoint()[0]
            else:
                point = geometry.asPoint()
            start_coordinates.append(f"{point.x()},{point.y()}")

        #dialog.log_message(f"coordenadas start quant: [{len(start_coordinates)}")
        # Ensure there are at least two points
        if len(start_coordinates) < 2:
            raise RuntimeError("At least two points are required for least-cost path analysis.")

        # Use the first point as the start and the last point as the stop
        start_coord = start_coordinates[0]  # Single-element list
        stop_coord = start_coordinates[-1]  # Single-element list
        
        #dialog.log_message(f"coordenadas start: [{start_coordinates}")

        
        params_r_cost = {
            'input': land_use_layer,
            #'start_points': points_layer,
            'start_coordinates': start_coord,  # Start coordinates (east, north)
            'stop_coordinates': stop_coord,  # Stop coordinates (east, north)
            'output': cost_output_path,
            'outdir': direction_output_path,  # Output direction raster
            'memory': 2000, # allocate 2GB
            'max_cost': None,  # Optional max cost
            'GRASS_REGION_PARAMETER': None,  # Optional for region alignment
            'flags': 'c'  # Prevent adding a color table to the raster
        }
    
        result = processing.run("grass7:r.cost", params_r_cost)

        if not result.get('output') or not os.path.exists(cost_output_path):
            raise RuntimeError("r.cost failed: Cost raster not generated.")
        
        if not os.path.exists(direction_output_path):
            raise RuntimeError("r.cost failed: Direction raster not generated.")
        
        dialog.log_message(f"r.cost generated cost raster: {cost_output_path}")
        dialog.log_message(f"r.cost generated direction raster: {direction_output_path}")
        
        # Return both cost and direction outputs
        return {
            'cost_raster': cost_output_path,
            'direction_raster': direction_output_path
        }
    except Exception as e:
        raise RuntimeError(f"Error running r.cost: {str(e)}")