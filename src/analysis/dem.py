from typing import TYPE_CHECKING
from qgis import processing

if TYPE_CHECKING:
    from ..dialog import Dialog
    
def create_slope_layer_from_dem(dialog: 'Dialog', dem_layer, output_path):
    dialog.log_message("Creating slope layer from DEM...")
    
    # note: dem_layer.rasterUnitsPerPixelX() -> this gets the width resolution of the pixel
    # dem resolution is 30 meters in this case
    # to do: later we need to figure it out this cuz dem and land use have different resolutions
    
    # note: check later if it is better to compute the slope layer using qgis:hillshade
    # that is a simpler but less customizable tool instead of using grass7:r.slope.aspect
    # it could be faster, but i need to check that as well
    
    try:
        params = {
            'elevation': dem_layer,
            'format': 0,  # degrees (0), percent (1)
            'zscale': 1.0,
            'min_slope': 0.0,
            'slope': output_path,
            'GRASS_REGION_PARAMETER': dem_layer.extent(),
            'GRASS_REGION_CELLSIZE_PARAMETER': dem_layer.rasterUnitsPerPixelX()
        }
        
        result = processing.run("grass7:r.slope.aspect", params)
        dialog.log_message(f"DEM slope layer created in path: {result['slope']}")
        return result['slope']

    except Exception as e:
        dialog.log_message(f"Error creating slope layer from DEM: {str(e)}")
        raise RuntimeError(f"Failed to create slope layer: {str(e)}")
