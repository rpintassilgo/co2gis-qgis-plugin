from qgis.core import QgsRasterLayer, QgsVectorLayer, QgsRaster, QgsPointXY, QgsFeatureRequest
from PyQt5.QtWidgets import QMessageBox
import numpy as np
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer

def calculate_pipeline_costs(dialog):
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

        # Read raster values along full pipeline
        full_raster_values = extract_raster_values(pipeline_layer, land_use_layer, slope_layer)
        if not full_raster_values:
            dialog.log_message("Error: No valid raster values found for pipeline path.")
            return

        # Get all input parameters
        λ = float(dialog.frictionFactorInput.text())
        M = float(dialog.massFlowRateInput.text())
        p = float(dialog.co2densityInput.text())
        Δp = float(dialog.pressureDropInput.text()) * 1000  # MPa/km → Pa/m
        Bc = float(dialog.standardizedCostInput.text())
        N = float(dialog.numInfrastructureInput.text())

        # Initialize
        total_cost = 0
        total_length = 0
        segment_costs = []
        booster_costs = []
        segment_index = 0

        max_segment_length = 150000  # 150 km in meters
        current_segment = []
        current_segment_length = 0
        sub_segment_index = 1  # Tracks internal cell index for debug

        for Fs, Flu, cell_length in full_raster_values:
            current_segment.append((Fs, Flu, cell_length))
            total_length += cell_length
            current_segment_length += cell_length

            segment_complete = current_segment_length >= max_segment_length
            final_segment = (total_length >= sum(cl for _, _, cl in full_raster_values))

            if segment_complete or final_segment:
                # Calculate D using this segment length
                L_segment = current_segment_length
                D = ((8 * λ * M**2 * L_segment) / (np.pi**2 * p * Δp))**(1/5)

                # Compute summation part of I_p
                summation = 0
                for Fs_i, Flu_i, cl_i in current_segment:
                    cost_factor = Fs_i * (Flu_i * (1 - 0.1 * N) + 0.1 * N)
                    segment_cost = cost_factor * cl_i
                    summation += segment_cost

                    # Debug message per cell — ENABLE IF NEEDED
                    # dialog.log_message(
                    #     f"Segment {segment_index+1}.{sub_segment_index}: L_cell = {cl_i:.2f} m, "
                    #     f"Fs = {Fs_i:.2f}, Flu = {Flu_i:.2f}, Segment Cost = {segment_cost:.2f} €"
                    # )
                    sub_segment_index += 1

                Ip = Bc * D * summation
                segment_costs.append(Ip)
                dialog.log_message(f"Segment {segment_index+1}: D = {D:.4f} m, Segment Cost (Ip) = {Ip:,.2f} €")

                # Add booster if not the last segment
                if not final_segment:
                    Beff = 0.75
                    Sc = (M * Δp) / (p * Beff)
                    Ib = 0.547 * Sc + 0.42
                    booster_costs.append(Ib)
                    dialog.log_message(f"Booster Cost (Ib) added: {Ib:,.2f} €")

                # Reset for next segment
                current_segment = []
                current_segment_length = 0
                sub_segment_index = 1
                segment_index += 1

        I_total = sum(segment_costs) + sum(booster_costs)
        dialog.log_message(f"Calculated pipeline price (Itotal): {I_total:,.2f} €")

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
