from qgis.core import QgsRasterLayer, QgsVectorLayer, QgsRaster, QgsPointXY, QgsFeatureRequest
from PyQt5.QtWidgets import QMessageBox
import numpy as np
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer

def calculate_pipeline_costs(dialog):
    """
    Calculate pipeline cost using given formulas.
    Includes detailed logging for debugging.
    """

    try:
        dialog.log_message("Calculating pipeline price...")

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
        raster_values = extract_raster_values(pipeline_layer, land_use_layer, slope_layer)

        if not raster_values:
            dialog.log_message("Error: No valid raster values found for pipeline path.")
            return

        # Calculate pipeline diameter D
        λ = float(dialog.frictionFactorInput.text())
        M = float(dialog.massFlowRateInput.text())
        p = float(dialog.co2densityInput.text())

        # Convert MPa/km to Pa/m (SI units)
        Δp = float(dialog.pressureDropInput.text()) * 1000

        D = ((8 * λ * M**2 * pipeline_length) / (np.pi**2 * p * Δp))**(1/5)

        dialog.log_message(f"Calculated pipeline diameter (D): {D:.4f} m")

        # Get other inputs
        Bc = float(dialog.standardizedCostInput.text())
        N = float(dialog.numInfrastructureInput.text())

        # Initialize accumulators
        total_sum = 0
        total_length = 0
        segment_index = 1

        for Fs, Flu, cell_length in raster_values:
            cost_factor = Fs * (Flu * (1 - 0.1 * N) + 0.1 * N)
            segment_cost = cost_factor * cell_length
            total_sum += segment_cost
            total_length += cell_length

            # Debug each summation iteration
            #dialog.log_message(
            #    f"Segment {segment_index}: L_cell = {cell_length:.2f} m, "
            #    f"Fs = {Fs:.2f}, Flu = {Flu:.2f}, Segment Cost = {segment_cost:.2f} €"
            #)
            segment_index += 1

        #dialog.log_message(f"Total summed L_cell (from segments): {total_length:.2f} m")
        #dialog.log_message(f"Total summation result: {total_sum:.2f}")

        # Final cost calculation
        I = Bc * D * total_sum

        dialog.log_message(f"Calculated pipeline price (I): {I:,.2f} €")

    except Exception as e:
        QMessageBox.critical(None, "Error", f"An error occurred: {str(e)}")
        dialog.log_message(f"Error: {str(e)}")

def extract_raster_values(pipeline_layer, land_use_layer, slope_layer):
    """
    This function extracts raster values at multiple points along each segment of the pipeline.
    It returns a list of tuples (Fs, Flu, cell_length), using the maximum value for each raster per segment.
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

                # Calculate intermediate points at 0%, 25%, 50%, 75%, and 100%
                sample_ratios = [0.0, 0.25, 0.5, 0.75, 1.0]
                land_use_vals = []
                slope_vals = []

                for ratio in sample_ratios:
                    x = start.x() + (end.x() - start.x()) * ratio
                    y = start.y() + (end.y() - start.y()) * ratio
                    point = QgsPointXY(x, y)

                    Fs = get_raster_value(land_use_layer, point)
                    Flu = get_raster_value(slope_layer, point)

                    if Fs is not None:
                        land_use_vals.append(Fs)
                    if Flu is not None:
                        slope_vals.append(Flu)

                # Use maximum value from the samples
                if land_use_vals and slope_vals:
                    max_Fs = max(land_use_vals)
                    max_Flu = max(slope_vals)
                    values.append((max_Fs, max_Flu, cell_length))

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
