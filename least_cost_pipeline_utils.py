from qgis import processing
from qgis.core import QgsProcessingFeedback

def run_r_cost(terrain_layer, points_layer):
    """Run r.cost on the selected terrain and start points layers."""
    params_r_cost = {
        'input': terrain_layer,
        'start_points': points_layer,
        'output': 'TEMPORARY_OUTPUT'
    }
    return processing.run("grass7:r.cost", params_r_cost, feedback=QgsProcessingFeedback())

def run_r_drain(cost_result, points_layer):
    """Run r.drain using the result from r.cost and the points layer."""
    params_r_drain = {
        'input': cost_result['output'],
        'start_points': points_layer,
        'output': 'TEMPORARY_OUTPUT'
    }
    return processing.run("grass7:r.drain", params_r_drain, feedback=QgsProcessingFeedback())
