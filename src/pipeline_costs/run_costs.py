from qgis.core import QgsRasterLayer, QgsVectorLayer, QgsRaster, QgsPointXY, QgsFeatureRequest
from PyQt5.QtWidgets import QMessageBox
import numpy as np
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer

def calculate_pipeline_costs(dialog):
    """
    Calculate pipeline cost using given formulas.
    """

    try:
        dialog.log_message("Calculating Pipeline price..")
        
        # Get pipeline vector layer
        pipeline_layer = get_layer_by_name(dialog.pipelineVectorDropdown.currentText())
        if not pipeline_layer:
            dialog.log_message("Error: Pipeline vector layer not found.")
            return

        # Get raster layers
        land_use_layer = get_layer_by_name(dialog.landUseCostsDropdown.currentText())
        slope_layer = get_layer_by_name(dialog.slopeCostsDropdown.currentText())

        if not land_use_layer or not slope_layer:
            dialog.log_message("Error: Land use or slope cost raster not found.")
            return

        # Get pipeline length
        pipeline_length = float(dialog.pipelineLengthInput.text())

        # Read raster values at pipeline locations
        raster_values = extract_raster_values(dialog, pipeline_layer, land_use_layer, slope_layer)

        # If no values are found, return
        if not raster_values:
            dialog.log_message("Error: No valid raster values found for pipeline path.")
            return

        # Calculate D (pipeline diameter)
        λ = float(dialog.frictionFactorInput.text())
        M = float(dialog.massFlowRateInput.text())
        p = float(dialog.co2densityInput.text())
        Δp = float(dialog.pressureDropInput.text())

        D = ((8 * λ * M**2 * pipeline_length) / (np.pi**2 * p * Δp))**(1/5)

        # Calculate I (pipeline cost)
        Bc = float(dialog.standardizedCostInput.text())
        N = float(dialog.numInfrastructureInput.text())
        total_sum = sum((Fs * (Flu * (1 - 0.1 * N) + 0.1 * N) * cell_length)
                        for Fs, Flu, cell_length in raster_values)

        I = Bc * D * total_sum

        # Display result
        dialog.log_message(f"Pipeline Prince calculated successfully: {I:.2f} €")
    
    except Exception as e:
        QMessageBox.critical(None, "Error", f"An error occurred: {str(e)}")
        dialog.log_message(f"Error: {str(e)}")

def extract_raster_values(pipeline_layer, land_use_layer, slope_layer):
    """
    This function extracts raster values where the pipeline vector passes through.
    It returns a list of tuples (Fs, Flu, cell_length).
    """
    values = []

    for feature in pipeline_layer.getFeatures():
        geom = feature.geometry()

        if geom.isMultipart():
            parts = geom.asMultiPolyline()
        else:
            parts = [geom.asPolyline()]

        for line in parts:
            for i in range(len(line) - 1):
                start, end = line[i], line[i + 1]
                cell_length = start.distance(end)

                # get raster values at the midpoint
                mid_x = (start.x() + end.x()) / 2
                mid_y = (start.y() + end.y()) / 2
                point = QgsPointXY(mid_x, mid_y)

                Fs = get_raster_value(land_use_layer, point)
                Flu = get_raster_value(slope_layer, point)

                if Fs is not None and Flu is not None:
                    values.append((Fs, Flu, cell_length))

    return values

def get_raster_value(raster_layer, point):
    """
    Get the raster value at a specific point.
    """
    provider = raster_layer.dataProvider()
    ident = provider.identify(point, QgsRaster.IdentifyFormatValue)
    
    if ident.isValid():
        # assuming a single band
        return list(ident.results().values())[0]
    return None

def get_layer_by_name(layer_name):
    """
    Retrieve a QGIS layer by its name.
    """
    layers = QgsProject.instance().mapLayers().values()
    for layer in layers:
        if layer.name() == layer_name:
            return layer
    return None
