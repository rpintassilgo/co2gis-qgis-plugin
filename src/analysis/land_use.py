from typing import TYPE_CHECKING
from qgis import processing

if TYPE_CHECKING:
    from ..complete_dialog import Dialog

# note: for some reason raster qgis:rastercalculator is very slow,
# maybe try later check for alternatives
# theres one called gdal that is command line tool designed for raster calculations
# the bad part is that it needs to be installed on the system, so theres that.
# but yeah it is necessary to analyse it better, if its possible if theres permissions
# to install it directly from the plugin or even other alternatives

# it is necessart to review this function, it is failing to calculate raster
def build_raster_calculator_expression(land_use_layer, class_costs):
    expression_parts = []
    max_cost = max(class_costs.values())
    undefined_cost = max_cost + 1   # assign undefined classes the highest cost + 1

    # generate expressions for each class ID
    for class_id, cost in class_costs.items():
        expression_parts.append(f'("{land_use_layer.name()}@1" = {class_id}) * {cost}')

    # combine all class expressions with "+" (addition)
    combined_expression = " + ".join(expression_parts)

    # add a fallback for undefined classes
    undefined_condition = " + ".join(
        [f'("{land_use_layer.name()}@1" != {class_id}) * {undefined_cost}' for class_id in class_costs]
    )

    final_expression = f"({combined_expression}) + ({undefined_condition})"
    return final_expression



def get_land_use_costs_raster(land_use_layer, class_costs, output_path):
    expression = build_raster_calculator_expression(land_use_layer, class_costs)
    
    # get dynamic cell size
    extent = land_use_layer.extent()
    cellsize_x = extent.width() / land_use_layer.width()
    cellsize_y = extent.height() / land_use_layer.height()
    cellsize = min(cellsize_x, cellsize_y)

    # Note: cell size is the resolution of the raster, basically what one pixel represents
    # cell size should be in the same unit as the raster's CRS, since i'm using EPSG:3763
    # that uses meters i can use meters
    # land use raster resolution is 10 meters
    params = {
        'EXPRESSION': expression,
        'LAYERS': [land_use_layer],
        'CELLSIZE': cellsize,
        'EXTENT': land_use_layer.extent(),
        'CRS': land_use_layer.crs(),
        'OUTPUT': output_path
    }

    try:
        result = processing.run("qgis:rastercalculator", params)
        return result['OUTPUT']
    except Exception as e:
        raise RuntimeError(f"Raster calculator failed: {str(e)}")
