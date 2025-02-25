from typing import TYPE_CHECKING
from qgis import processing
from qgis.core import QgsRasterLayer

if TYPE_CHECKING:
    from ..complete_dialog import Dialog
    
def create_slope_layer_from_dem(dem_layer, output_path):
    try:
        params = {
            'INPUT': dem_layer,                  # Input DEM raster
            'BAND': 1,                           # Band number
            'SCALE': 1.0,                        # Ratio of vertical units to horizontal
            'AS_PERCENT': True,                  # Express slope as percent instead of degrees
            'COMPUTE_EDGES': False,              # Whether to compute edges
            'ZEVENBERGEN': False,                # Use ZevenbergenThorne formula
            'OPTIONS': '',                       # Additional creation options
            'OUTPUT': output_path                # Output path for the slope raster
        }

        # Run the GDAL Slope tool
        result = processing.run("gdal:slope", params)

        return result['OUTPUT']

    except Exception as e:
        raise RuntimeError(f"Failed to create slope layer: {str(e)}")

def build_slope_cost_expression(slope_layer, slope_costs: list):
    """
    Build a raster calculator expression based on slope intervals and their costs.
    
    Example expression:
    (("slope@1" < 10) * 1.0) +
    (("slope@1" >= 10 AND "slope@1" < 20) * 1.1) + ...
    """
    
    expression_parts = []

    for slope_range in slope_costs:
        min_slope = slope_range['min']
        max_slope = slope_range.get('max')
        cost = slope_range['cost']

        if max_slope is not None:
            # Range with upper limit
            expression = f'(("{slope_layer.name()}@1" >= {min_slope} and "{slope_layer.name()}@1" < {max_slope}) * {cost})'
        else:
            # No upper limit (e.g., slope >= 70)
            expression = f'(("{slope_layer.name()}@1" >= {min_slope}) * {cost})'

        expression_parts.append(expression)

    # Combine expressions with "+"
    final_expression = " + ".join(expression_parts)
    
    print("Generated Expression:\n", final_expression)

    return final_expression
    
def create_slope_costs_from_slope(slope_layer, slope_costs, output_path):
    """Create slope cost raster using the raster calculator."""

    # Build expression
    expression = build_slope_cost_expression(slope_layer, slope_costs)

    # Get raster resolution
    extent = slope_layer.extent()
    cellsize_x = extent.width() / slope_layer.width()
    cellsize_y = extent.height() / slope_layer.height()
    cellsize = min(cellsize_x, cellsize_y)

    # Raster Calculator Params
    params = {
        'EXPRESSION': expression,
        'LAYERS': [slope_layer],
        'CELLSIZE': cellsize,
        'EXTENT': extent,
        'CRS': slope_layer.crs(),
        'OUTPUT': output_path
    }

    try:
        result = processing.run("qgis:rastercalculator", params)
        return result['OUTPUT']
    except Exception as e:
        raise RuntimeError(f"Slope cost raster calculation failed: {str(e)}")
    