from qgis import processing
from .path import get_plugin_output_path
import os

os.environ["GRASS_VERBOSE"] = "3"  # Enable GRASS debugging

def run_r_cost(land_use_layer, points_layer):
    output_path = get_plugin_output_path("r_cost_output.tif")
    
    params_r_cost = {
        'input': land_use_layer,
        'start_points': points_layer,
        'output': output_path,
        'memory': 2000 # Allocate 2GB
    }
    
    try:
        result = processing.run("grass7:r.cost", params_r_cost)

        # Validate the result
        if 'output' not in result or not result['output']:
            print("RESULTDO DO R.COST INVALIDO")

        return result
    except Exception as e:
        raise RuntimeError(f"Error running r.cost: {str(e)}")