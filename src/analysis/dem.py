from typing import TYPE_CHECKING
from qgis import processing

if TYPE_CHECKING:
    from ..complete_dialog import Dialog
    
def create_slope_layer_from_dem(dem_layer, output_path):
    try:
        params = {
            'INPUT': dem_layer,  # Input DEM raster layer or path
            'Z_FACTOR': 1.0,  # Vertical exaggeration factor
            'OUTPUT': output_path  # Output path for slope raster
        }

        # Run the slope calculation
        result = processing.run("qgis:slope", params)

        return result['OUTPUT']

    except Exception as e:
        raise RuntimeError(f"Failed to create slope layer: {str(e)}")