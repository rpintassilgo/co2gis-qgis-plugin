from qgis import processing

def run_r_drain(cost_result, points_layer, vector_output_path):
    try:
        # Step 1: Run r.drain
        params_r_drain = {
            'input': cost_result['output'],  # Raster from r.cost
            'start_points': points_layer,
            'output': 'TEMPORARY_OUTPUT',  # r.drain raster output
        }
        drain_result = processing.run("grass7:r.drain", params_r_drain)
    
        # Step 2: Convert raster to vector
        drain_raster_output = drain_result['output']
        processing.run("gdal:polygonize", {
            'INPUT': drain_raster_output,
            'BAND': 1,
            'FIELD': 'DN',  # Attribute field name
            'OUTPUT': vector_output_path
        })

        return vector_output_path
    except Exception as e:
        raise RuntimeError(f"Error running r.cost: {str(e)}")
