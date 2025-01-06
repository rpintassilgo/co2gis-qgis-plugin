from .path import get_plugin_output_path
from qgis import processing
import os
from qgis.core import QgsVectorLayer, QgsProject

def run_r_drain_and_load(cost_result, points_layer, output_vector_path):
    """
    Runs r.drain, converts the result to vector with r.to.vect, and loads it into QGIS.
    """
    try:
        # Step 1: Run r.drain
        print("Running r.drain...")
        drain_raster_path = get_plugin_output_path("drain_output.tif")
        params_r_drain = {
            'input': cost_result['cost_raster'],  # Input raster from r.cost
            'direction': cost_result['direction_raster'],
            'start_points': points_layer,
            'output': drain_raster_path,
            'GRASS_REGION_PARAMETER': None,
            'GRASS_REGION_CELLSIZE_PARAMETER': 0,
            'GRASS_RASTER_FORMAT_OPT': '',
            'GRASS_RASTER_FORMAT_META': '',
        }
        print(f"r.drain parameters: {params_r_drain}")
        processing.run("grass7:r.drain", params_r_drain)

        # Verify r.drain output
        if not os.path.exists(drain_raster_path):
            raise RuntimeError(f"r.drain failed: Output raster not created: {drain_raster_path}")
        print(f"r.drain output created: {drain_raster_path}")

        # Step 2: Convert raster to vector lines using r.to.vect
        print("Running r.to.vect...")
        params_r_to_vect = {
            'input': drain_raster_path,
            'type': 1,  # 1 corresponds to "line" in GRASS
            'output': output_vector_path,
            'GRASS_REGION_PARAMETER': None,
            'GRASS_REGION_CELLSIZE_PARAMETER': 0,
        }
        print(f"r.to.vect parameters: {params_r_to_vect}")
        processing.run("grass7:r.to.vect", params_r_to_vect)

        # Verify r.to.vect output
        if not os.path.exists(output_vector_path):
            raise RuntimeError(f"r.to.vect failed: Vector file not created: {output_vector_path}")
        print(f"r.to.vect output created: {output_vector_path}")

        # Step 3: Load the vector layer into QGIS
        print("Loading vector layer into QGIS...")
        vector_layer = QgsVectorLayer(output_vector_path, "Least Cost Path Vector", "ogr")
        if vector_layer.isValid():
            QgsProject.instance().addMapLayer(vector_layer)
            print("Vector layer successfully added to QGIS.")
        else:
            raise RuntimeError(f"Failed to load vector layer: {output_vector_path}")

    except Exception as e:
        print(f"Error: {str(e)}")