from qgis import processing

def run_r_drain(cost_result, points_layer):
    params_r_drain = {
        'input': cost_result['output'],
        'start_points': points_layer,
        'output': 'TEMPORARY_OUTPUT'
    }
    
    try:
        result = processing.run("grass7:r.drain", params_r_drain)
        
        # Validate the result
        if 'output' not in result or not result['output']:
            print("RESULTDO DO R.DRAIN INVALIDO")
        
        return result
    except Exception as e:
        raise RuntimeError(f"Error running r.cost: {str(e)}")
