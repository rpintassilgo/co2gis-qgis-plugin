from qgis import processing
import os
from qgis.core import QgsVectorLayer, QgsProject

def run_r_drain_and_load(cost_result, points_layer, output_drain_raster, output_vector_path):
    """
    Runs r.drain to generate a least-cost path and ensures vector output.
    """
    try:
        vector_layer: QgsVectorLayer = points_layer

        # Get the coordinates of the START POINT from the vector layer
        start_coordinates = []
        for feature in vector_layer.getFeatures():
            geometry = feature.geometry()
            if geometry.isMultipart():
                point = geometry.asMultiPoint()[0]
            else:
                point = geometry.asPoint()
            start_coordinates.append(f"{point.x()},{point.y()}")

        if len(start_coordinates) < 1:
            raise RuntimeError("At least one start point is required for r.drain.")

        end_coord = start_coordinates[-1]

        # Run r.drain with raster output first
        params_r_drain = {
            'input': cost_result['cost_raster'],  # Cumulative cost raster
            'direction': cost_result['direction_raster'],  # Movement directions raster
            'start_coordinates': end_coord,  # Start point of the path
            'output': output_drain_raster,  # First output is a raster
            'drain': output_vector_path,
            'GRASS_REGION_PARAMETER': None,
            'GRASS_REGION_CELLSIZE_PARAMETER': 0,
            'flags': 'c'  # 's' ensures a single path
        }

        print(f"Running r.drain with parameters: {params_r_drain}")
        result = processing.run("grass7:r.drain", params_r_drain)

        # Verify r.drain raster output
        if not os.path.exists(output_drain_raster):
            raise RuntimeError(f"r.drain failed: Output raster not created: {output_drain_raster}")

        # Step 2: Convert raster to vector using r.to.vect
        #params_r_to_vect = {
        #    'input': output_drain_raster,
        #    'type': 2,  # Type 1 = Line
        #    'output': output_vector_path,
        #    'GRASS_REGION_PARAMETER': None,
        #    'GRASS_REGION_CELLSIZE_PARAMETER': 0
        #}

        #print(f"Running r.to.vect with parameters: {params_r_to_vect}")
        #processing.run("grass7:r.to.vect", params_r_to_vect)

        # Verify r.to.vect output
        if not os.path.exists(output_vector_path):
            raise RuntimeError(f"r.to.vect failed: Output vector not created: {output_vector_path}")

        # Load vector output into QGIS
        vector_layer = QgsVectorLayer(output_vector_path, "Least Cost Path", "ogr")
        if vector_layer.isValid():
            QgsProject.instance().addMapLayer(vector_layer)
            print("Vector layer successfully added to QGIS.")
        else:
            raise RuntimeError(f"Failed to load vector layer: {output_vector_path}")

    except Exception as e:
        raise RuntimeError(f"Error in r.drain: {str(e)}")
