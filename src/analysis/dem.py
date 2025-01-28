from typing import TYPE_CHECKING
from qgis import processing

if TYPE_CHECKING:
    from ..complete_dialog import Dialog
    
def create_slope_layer_from_dem(dialog: 'Dialog', dem_layer, output_path):
    dialog.log_message("Creating slope layer from DEM using qgis:slope...")

    try:
        params = {
            'INPUT': dem_layer,  # Input DEM raster layer or path
            'Z_FACTOR': 1.0,  # Vertical exaggeration factor
            'OUTPUT': output_path  # Output path for slope raster
        }

        # Run the slope calculation
        result = processing.run("qgis:slope", params)
        dialog.log_message(f"Slope layer created successfully at: {result['OUTPUT']}")

        return result['OUTPUT']

    except Exception as e:
        dialog.log_message(f"Error creating slope layer from DEM: {str(e)}")
        raise RuntimeError(f"Failed to create slope layer: {str(e)}")