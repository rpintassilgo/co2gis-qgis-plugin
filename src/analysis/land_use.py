from qgis import processing

# it is necessart to review this function, it is failing to calculate raster
def build_raster_calculator_expression(land_use_layer, class_costs):
    expression_parts = []

    for class_id, cost in class_costs.items():
        expression_parts.append(f'("{land_use_layer.name()}" = {class_id}) * {cost}')

    # Combine all expressions with addition
    return " + ".join(expression_parts)

def get_land_use_costs_raster(land_use_layer, class_costs, output_path):
    expression = build_raster_calculator_expression(land_use_layer, class_costs)

    params = {
        'EXPRESSION': expression,
        'LAYERS': [land_use_layer],
        'CELLSIZE': 0,  # Use the input layer's cell size
        'EXTENT': land_use_layer.extent(),
        'CRS': land_use_layer.crs(),
        'OUTPUT': output_path
    }

    try:
        result = processing.run("qgis:rastercalculator", params)
        return result['OUTPUT']
    except Exception as e:
        raise RuntimeError(f"Raster calculator failed: {str(e)}")
