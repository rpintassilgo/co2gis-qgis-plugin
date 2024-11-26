from typing import TYPE_CHECKING
from qgis import processing
from .path import get_plugin_output_path
import os

if TYPE_CHECKING:
    from ..dialog import Dialog
    
os.environ["GRASS_VERBOSE"] = "3"  # Enable GRASS debugging

def combine_rasters_with_weights(dialog: 'Dialog', costs_raster, slope_raster, dem_weight, occupancy_weight, output_path):
    try:
        dialog.log_message("Combining land use costs raster and slope raster with weights...")

        # build the raster calculator expression
        expression = (
            f"({occupancy_weight} * \"{costs_raster}@1\") + "
            f"({dem_weight} * \"{slope_raster}@1\")"
        )
        
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

def run_r_cost(land_use_layer, points_layer):
    output_path = get_plugin_output_path("r_cost_output.tif")
    
    params_r_cost = {
        'input': land_use_layer,
        'start_points': points_layer,
        'output': output_path,
        'memory': 2000 # allocate 2GB
    }
    
    try:
        result = processing.run("grass7:r.cost", params_r_cost)

        if 'output' not in result or not result['output']:
            print("RESULTDO DO R.COST INVALIDO")

        return result
    except Exception as e:
        raise RuntimeError(f"Error running r.cost: {str(e)}")