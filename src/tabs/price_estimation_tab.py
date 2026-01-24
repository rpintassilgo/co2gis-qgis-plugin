from typing import TYPE_CHECKING
import numpy as np
from PyQt5.QtWidgets import (
    QLabel, QComboBox, QLineEdit, QPushButton, QHBoxLayout, QFormLayout, 
    QGroupBox, QVBoxLayout, QDialog, QGridLayout
)
from PyQt5.QtCore import Qt
from qgis.core import QgsProject, QgsRaster, QgsPointXY, QgsGeometry

from ..task_manager import run_in_background
from ..utils import update_pipeline_length, update_resolution_field

if TYPE_CHECKING:
    from ..analysis_dialog import AnalysisDialog

def setup_price_estimation_tab(dialog: 'AnalysisDialog', layout: QVBoxLayout):
    """Sets up the UI for the Price Estimation tab."""
    main_layout = QVBoxLayout()
    columns_layout = QHBoxLayout()
    left_layout = QVBoxLayout()
    right_layout = QVBoxLayout()
    columns_layout.addLayout(left_layout, 1)
    columns_layout.addLayout(right_layout, 1)

    # ... (rest of the setup from ui.py)
    descriptionGroupBox = QGroupBox()
    descriptionGroupBox.setStyleSheet("QGroupBox { border: 0px; }")
    descriptionLayout = QFormLayout()
    descriptionLabel = QLabel("""
        <html>
            <body>
                <p style="text-align:justify; font-size:11px; color:lightgrey;">
                    ⓘ This submenu calculates the total pipeline cost (<b>I<sub>total</sub></b>) based on its length.
                    The pipeline diameter (<b>D</b>) is calculated using the total pipeline length (<b>L</b>). <br>
                    If the pipeline is <b>150 km or less</b>, the cost is calculated using a single <b>I<sub>P</sub></b>. <br> 
                    If the pipeline is longer than <b>150 km</b>, it is split into <b>segments of up to 150 km</b>, 
                    and multiple <b>I<sub>P</sub></b> values are calculated. <br>
                    <b>L<sub>cell</sub></b> represents the pipeline length inside each GIS cell. <br>
                    Booster stations are added after every 150 km, and their costs (<b>I<sub>B</sub></b>)
                    are included in <b>I<sub>total</sub></b>.
                </p>
            </body>
        </html>
    """)
    descriptionLayout.addRow(descriptionLabel)
    descriptionGroupBox.setLayout(descriptionLayout)
    main_layout.addWidget(descriptionGroupBox)

    dialog.show_formulas_button = QPushButton("Show Calculation Formulas")
    main_layout.addWidget(dialog.show_formulas_button)
    
    main_layout.addLayout(columns_layout)

    selectionGroupBox = QGroupBox()
    selectionGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")
    selectionLayout = QFormLayout()
    selectionTitle = QLabel("Select Cost Rasters and Vector")
    selectionTitle.setAlignment(Qt.AlignCenter)
    selectionTitle.setStyleSheet("font-weight: bold; font-size: 12px;")
    selectionLayout.addRow(selectionTitle)
    dialog.pipelineVectorDropdown = QComboBox()
    dialog.landUseCostsDropdown = QComboBox()
    dialog.slopeCostsDropdown = QComboBox()
    dialog.corridorsCostsDropdown = QComboBox()
    dialog.crossingsCostsDropdown = QComboBox()
    selectionLayout.addRow(QLabel("Select Pipeline Vector:"), dialog.pipelineVectorDropdown)
    selectionLayout.addRow(QLabel("Select Land Use Costs Raster (F<sub>lu</sub>):"), dialog.landUseCostsDropdown)
    selectionLayout.addRow(QLabel("Select Slope Costs Raster (F<sub>s</sub>):"), dialog.slopeCostsDropdown)
    selectionLayout.addRow(QLabel("Select Corridors Costs Raster (F<sub>c</sub>):"), dialog.corridorsCostsDropdown)
    selectionLayout.addRow(QLabel("Select Crossings Costs Raster (F<sub>ci</sub>):"), dialog.crossingsCostsDropdown)
    
    dialog.landUseCostsResInput = QLineEdit()
    dialog.slopeCostsResInput = QLineEdit()
    dialog.corridorsCostsResInput = QLineEdit()
    dialog.crossingsCostsResInput = QLineEdit()
    selectionLayout.addRow(QLabel("Land Use Costs Resolution:"), dialog.landUseCostsResInput)
    selectionLayout.addRow(QLabel("Slope Costs Resolution:"), dialog.slopeCostsResInput)
    selectionLayout.addRow(QLabel("Corridors Costs Resolution:"), dialog.corridorsCostsResInput)
    selectionLayout.addRow(QLabel("Crossings Costs Resolution:"), dialog.crossingsCostsResInput)
    selectionGroupBox.setLayout(selectionLayout)
    left_layout.addWidget(selectionGroupBox)

    inputGroupBox = QGroupBox()
    inputGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")
    inputLayout = QFormLayout()
    inputTitle = QLabel("Equation Input Variables")
    inputTitle.setAlignment(Qt.AlignCenter)
    inputTitle.setStyleSheet("font-weight: bold; font-size: 12px;")
    inputLayout.addRow(inputTitle)
    dialog.pipelineLengthInput = QLineEdit()
    dialog.pipelineLengthInput.setReadOnly(True)
    dialog.crossingsVectorDropdown = QComboBox()
    dialog.standardizedCostFactorInput = QLineEdit()
    dialog.frictionFactorInput = QLineEdit()
    dialog.co2MassFlowRateInput = QLineEdit()
    dialog.co2densityInput = QLineEdit()
    dialog.pressureDropInput = QLineEdit()
    
    dialog.standardizedCostFactorInput.setText("1357")
    dialog.frictionFactorInput.setText("0.015")
    dialog.co2MassFlowRateInput.setText("1")
    dialog.co2densityInput.setText("827")
    dialog.pressureDropInput.setText("0.02")
    
    inputLayout.addRow(QLabel("Pipeline Length (L, in m):"), dialog.pipelineLengthInput)
    inputLayout.addRow(QLabel("Select Infrastructure Crossings Vector (N):"), dialog.crossingsVectorDropdown)
    inputLayout.addRow(QLabel("Standardized Cost Factor (B<sub>c</sub>, in €/m²):"), dialog.standardizedCostFactorInput)
    inputLayout.addRow(QLabel("Friction Factor (λ):"), dialog.frictionFactorInput)
    inputLayout.addRow(QLabel("CO2 Mass Flow Rate (M, in kg/s):"), dialog.co2MassFlowRateInput)
    inputLayout.addRow(QLabel("CO2 Density (ρ, in kg/m³):"), dialog.co2densityInput)
    inputLayout.addRow(QLabel("Admissible Pressure Drop (Δp/L, in MPa/km):"), dialog.pressureDropInput)
    inputGroupBox.setLayout(inputLayout)
    right_layout.addWidget(inputGroupBox)
    
    dialog.calculatePriceButton = QPushButton("Calculate pipeline price")
    main_layout.addWidget(dialog.calculatePriceButton)

    layout.addLayout(main_layout)

def connect_price_estimation_signals(dialog: 'AnalysisDialog'):
    """Connects signals for the Price Estimation tab."""
    dialog.calculatePriceButton.clicked.connect(lambda checked: run_in_background(dialog, run_price_estimation))
    dialog.show_formulas_button.clicked.connect(lambda: open_formulas_dialog(dialog))
    
    dialog.pipelineVectorDropdown.currentIndexChanged.connect(lambda: update_pipeline_length(dialog))
    dialog.landUseCostsDropdown.currentIndexChanged.connect(
        lambda: update_resolution_field(dialog, dialog.landUseCostsDropdown, dialog.landUseCostsResInput)
    )
    dialog.slopeCostsDropdown.currentIndexChanged.connect(
        lambda: update_resolution_field(dialog, dialog.slopeCostsDropdown, dialog.slopeCostsResInput)
    )
    dialog.corridorsCostsDropdown.currentIndexChanged.connect(
        lambda: update_resolution_field(dialog, dialog.corridorsCostsDropdown, dialog.corridorsCostsResInput)
    )
    dialog.crossingsCostsDropdown.currentIndexChanged.connect(
        lambda: update_resolution_field(dialog, dialog.crossingsCostsDropdown, dialog.crossingsCostsResInput)
    )

def run_price_estimation(dialog: 'AnalysisDialog'):
    """Calculates the total pipeline price based on various cost factors."""
    try:
        dialog.log_message("Calculating pipeline price...", "Price Estimation")

        pipeline_layer = QgsProject.instance().mapLayer(dialog.pipelineVectorDropdown.currentData())
        land_use_layer = QgsProject.instance().mapLayer(dialog.landUseCostsDropdown.currentData())
        slope_layer = QgsProject.instance().mapLayer(dialog.slopeCostsDropdown.currentData())
        corridors_layer = QgsProject.instance().mapLayer(dialog.corridorsCostsDropdown.currentData())
        crossings_layer = QgsProject.instance().mapLayer(dialog.crossingsCostsDropdown.currentData())
        crossings_vector_layer = QgsProject.instance().mapLayer(dialog.crossingsVectorDropdown.currentData())
        
        if not all([pipeline_layer, land_use_layer, slope_layer, corridors_layer, crossings_layer, crossings_vector_layer]):
            raise ValueError("All layers for price estimation must be selected.")

        full_raster_values = extract_raster_values_along_pipeline(
            pipeline_layer, land_use_layer, slope_layer, corridors_layer, crossings_layer, crossings_vector_layer
        )
        if not full_raster_values:
            raise ValueError("No valid raster values found for the pipeline path. Check if the pipeline intersects with the cost rasters.")

        λ = float(dialog.frictionFactorInput.text())
        M = float(dialog.co2MassFlowRateInput.text())
        p = float(dialog.co2densityInput.text())
        Δp_per_length_unit = float(dialog.pressureDropInput.text()) * 1000  # MPa/km → Pa/m (pressure drop per meter)
        Bc = float(dialog.standardizedCostFactorInput.text())
        
        segment_costs = []
        booster_costs = []
        segment_index = 0
        total_length = 0

        max_segment_length = 150000  # 150 km
        current_segment_cells = []
        current_segment_length = 0
        
        pipeline_total_length = sum(cl for _, _, _, _, _, cl in full_raster_values)

        # Calculate total pressure drop for the entire pipeline
        ΔP = Δp_per_length_unit * pipeline_total_length  # Pa (total pressure drop)
        
        # Calculate diameter D once for the entire pipeline using total length
        dialog.log_message(f"DEBUG D CALC - λ (lambda): {λ}", "Price Estimation")
        dialog.log_message(f"DEBUG D CALC - M (mass flow): {M} kg/s", "Price Estimation")
        dialog.log_message(f"DEBUG D CALC - M²: {M**2}", "Price Estimation")
        dialog.log_message(f"DEBUG D CALC - Total Pipeline Length (L): {pipeline_total_length} m", "Price Estimation")
        dialog.log_message(f"DEBUG D CALC - ρ (rho/density): {p} kg/m³", "Price Estimation")
        dialog.log_message(f"DEBUG D CALC - Δp (pressure drop per meter): {Δp_per_length_unit} Pa/m", "Price Estimation")
        dialog.log_message(f"DEBUG D CALC - ΔP (total pressure drop, Δp×L): {ΔP:,.0f} Pa = {ΔP/1e6:.2f} MPa", "Price Estimation")
        dialog.log_message(f"DEBUG D CALC - π²: {np.pi**2}", "Price Estimation")
        
        # Calculate step by step
        numerator = 8 * λ * M**2 * pipeline_total_length
        denominator = np.pi**2 * p * ΔP
        fraction = numerator / denominator
        
        dialog.log_message(f"DEBUG D CALC - Numerator (8*λ*M²*L): {numerator:,.2f}", "Price Estimation")
        dialog.log_message(f"DEBUG D CALC - Denominator (π²*ρ*ΔP): {denominator:,.2f}", "Price Estimation")
        dialog.log_message(f"DEBUG D CALC - Fraction (num/den): {fraction:.8f}", "Price Estimation")
        dialog.log_message(f"DEBUG D CALC - Fraction^(1/5): {fraction**(1/5):.6f}", "Price Estimation")
        
        D = ((8 * λ * M**2 * pipeline_total_length) / (np.pi**2 * p * ΔP))**(1/5)
        dialog.log_message(f"Pipeline Diameter (D): {D:.4f} m = {D*1000:.0f} mm (constant for entire pipeline)", "Price Estimation")
        dialog.log_message(f"--------------------------------------------------", "Price Estimation")

        for Fc, Fs, Flu, Fci, N, cell_length in full_raster_values:
            current_segment_cells.append((Fc, Fs, Flu, Fci, N, cell_length))
            total_length += cell_length
            current_segment_length += cell_length

            segment_complete = current_segment_length >= max_segment_length
            final_segment = total_length >= pipeline_total_length

            if segment_complete or final_segment:
                L_segment = current_segment_length

                summation = sum(
                    fc_i * fs_i * (flu_i * (1 - 0.1 * n_i) + 0.1 * n_i * fci_i) * cl_i
                    for fc_i, fs_i, flu_i, fci_i, n_i, cl_i in current_segment_cells
                )

                # Debug logging for F factor values
                if current_segment_cells:
                    sample_fc, sample_fs, sample_flu, sample_fci, sample_n, sample_cl = current_segment_cells[0]
                    dialog.log_message(f"DEBUG - Sample F values: Fc={sample_fc:.2f}, Fs={sample_fs:.2f}, Flu={sample_flu:.2f}, Fci={sample_fci:.2f}, N={sample_n}, L_cell={sample_cl:.2f}", "Price Estimation")
                    
                dialog.log_message(f"DEBUG - Summation value: {summation:,.2f}", "Price Estimation")
                dialog.log_message(f"DEBUG - Bc={Bc}, D={D:.4f}m (constant), Segment_length={L_segment:.2f}m", "Price Estimation")
                
                # Show min/max F values across all cells in segment
                all_fc = [fc for fc, _, _, _, _, _ in current_segment_cells]
                all_fs = [fs for _, fs, _, _, _, _ in current_segment_cells]
                all_flu = [flu for _, _, flu, _, _, _ in current_segment_cells]
                all_fci = [fci for _, _, _, fci, _, _ in current_segment_cells]
                
                dialog.log_message(f"DEBUG - F ranges: Fc={min(all_fc):.2f}-{max(all_fc):.2f}, Fs={min(all_fs):.2f}-{max(all_fs):.2f}, Flu={min(all_flu):.2f}-{max(all_flu):.2f}, Fci={min(all_fci):.2f}-{max(all_fci):.2f}", "Price Estimation")

                Ip = Bc * D * summation
                segment_costs.append(Ip)
                dialog.log_message(f"Segment {segment_index+1}: Length = {L_segment:.2f} m, Cost (Ip) = {Ip:,.2f} €", "Price Estimation")

                if not final_segment:
                    # Booster stations are placed every 150 km
                    # Calculate pressure drop for 150 km segment
                    ΔP_booster_segment = Δp_per_length_unit * 150000  # Pa (pressure drop over 150 km)
                    Beff = 0.75
                    Sc_W = (M * ΔP_booster_segment) / (p * Beff) #W (compressor power)
                    Sc_MW = Sc_W / 1e6 # converted to MW
                    Ib = (0.547 * Sc_MW + 0.42) * 1e6 # Convert M€ to €
                    booster_costs.append(Ib)
                    dialog.log_message(f"Booster Station after 150 km: ΔP_segment = {ΔP_booster_segment/1e6:.2f} MPa, Sc = {Sc_MW:.2f} MW, Cost (Ib) = {Ib:,.2f} €", "Price Estimation")

                current_segment_cells = []
                current_segment_length = 0
                segment_index += 1

        I_total = sum(segment_costs) + sum(booster_costs)
        dialog.log_message(f"--------------------------------------------------", "Price Estimation")
        dialog.log_message(f"Calculated Total Pipeline Price (Itotal): {I_total:,.2f} €", "Price Estimation")
        dialog.log_message(f"--------------------------------------------------", "Price Estimation")


    except Exception as e:
        dialog.log_message(f"Price Estimation Failed: {str(e)}", "Price Estimation")

def extract_raster_values_along_pipeline(pipeline_layer, land_use_layer, slope_layer, corridors_layer, crossings_layer, crossings_vector_layer):
    """
    Extracts raster values at multiple points along each segment of the pipeline, returning the maximum value for each raster.
    """
    values = []
    crossings_features = list(crossings_vector_layer.getFeatures())

    for feature in pipeline_layer.getFeatures():
        geom = feature.geometry()
        parts = geom.asMultiPolyline() if geom.isMultipart() else [geom.asPolyline()]
        for line in parts:
            for i in range(len(line) - 1):
                start, end = line[i], line[i + 1]
                
                segment_geom = QgsGeometry.fromPolylineXY([start, end])
                num_intersections = 0
                for crossing_feature in crossings_features:
                    if segment_geom.intersects(crossing_feature.geometry()):
                        num_intersections += 1

                cell_length = start.distance(end)
                sample_ratios = [0.0, 0.25, 0.5, 0.75, 1.0]
                corridors_vals, land_use_vals, slope_vals, crossings_vals = [], [], [], []

                for ratio in sample_ratios:
                    x, y = start.x() + (end.x() - start.x()) * ratio, start.y() + (end.y() - start.y()) * ratio
                    point = QgsPointXY(x, y)
                    
                    Fc = get_raster_value_at_point(corridors_layer, point)
                    Fs = get_raster_value_at_point(slope_layer, point)
                    Flu = get_raster_value_at_point(land_use_layer, point)
                    Fci = get_raster_value_at_point(crossings_layer, point)

                    if Fc is not None: corridors_vals.append(Fc)
                    if Fs is not None: slope_vals.append(Fs)
                    if Flu is not None: land_use_vals.append(Flu)
                    if Fci is not None: crossings_vals.append(Fci)

                if all([land_use_vals, slope_vals, corridors_vals, crossings_vals]):
                    values.append((max(corridors_vals), max(slope_vals), max(land_use_vals), max(crossings_vals), num_intersections, cell_length))
    return values

def get_raster_value_at_point(raster_layer, point):
    """Gets a raster value at a specific point."""
    if not raster_layer: return None
    provider = raster_layer.dataProvider()
    ident = provider.identify(point, QgsRaster.IdentifyFormatValue)
    if ident.isValid() and ident.results():
        return list(ident.results().values())[0]
    return None

def open_formulas_dialog(parent_dialog):
    """Opens the dialog that displays the formulas."""
    dialog = FormulaDialog(parent_dialog)
    dialog.exec_()

class FormulaDialog(QDialog):
    """A simple dialog to display the formulas in a grid."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calculation Formulas")
        self.setStyleSheet("""
            QDialog { background-color: #2a2a2a; }
            QLabel { color: white; }
        """)
        
        grid_layout = QGridLayout()
        # ... (rest of the FormulaDialog from ui.py)
        grid_layout.setSpacing(20)
        grid_layout.setColumnStretch(1, 1)

        D_formula_label = QLabel("""
            <html><body><table align="center" border="0" cellspacing="0" cellpadding="5">
            <tr><td style="font-size:25px; font-weight:bold; text-align:right;">D</td><td style="font-size:25px; font-weight:bold; text-align:center;">=</td><td style="font-size:40px; font-weight:bold; text-align:center;">(</td><td>
            <table align="center" border="0" cellspacing="0" cellpadding="0"><tr><td style="text-align:center; font-size:18px; padding-bottom:2px;">8 ⋅ λ ⋅ M² ⋅ L</td></tr><tr><td style="border-top: 2px solid white; text-align:center; font-size:18px; padding-top:2px;">π² ⋅ &#961; ⋅ ΔP</td></tr></table>
            </td><td style="font-size:40px; font-weight:bold; text-align:center;">)</td><td style="font-size:22px; font-weight:bold; text-align:center;"><sup>1/5</sup></td></tr></table></body></html>""")
        D_explanation = QLabel("<b>Pipeline Diameter (D):</b><br>Calculated based on flow rate (M), fluid properties (λ, ρ), total pipeline length (L), and admissable pressure drop (ΔP)")
        D_explanation.setWordWrap(True)
        grid_layout.addWidget(D_formula_label, 1, 0, Qt.AlignCenter)
        grid_layout.addWidget(D_explanation, 1, 1)

        Ip_formula_label = QLabel("""
            <html><body><p align="center" style="font-size:25px; font-weight:bold;">
            I<sub>p</sub> = B<sub>c</sub> ⋅ D ⋅ Σ { F<sub>c</sub> ⋅F<sub>s</sub> ⋅ [F<sub>lu</sub> ⋅ (1 - 0.1N) + 0.1N ⋅ F<sub>ci</sub>] ⋅ L<sub>cell</sub> }</p></body></html>""")
        Ip_explanation = QLabel("<b>Pipeline Segment Cost (I<sub>p</sub>):</b><br>Determined by the standardized cost (B<sub>c</sub>), diameter (D), and a summation of various cost factors (F<sub>c</sub>, F<sub>s</sub>, F<sub>lu</sub>, F<sub>ci</sub>) and infrastructure crossings (N) over each cell's length (L<sub>cell</sub>).")
        Ip_explanation.setWordWrap(True)
        grid_layout.addWidget(Ip_formula_label, 2, 0, Qt.AlignCenter)
        grid_layout.addWidget(Ip_explanation, 2, 1)

        Sc_formula_label = QLabel("""
            <html><body><table align="center" border="0" cellspacing="0" cellpadding="5">
            <tr><td style="font-size:25px; font-weight:bold; text-align:right;">S<sub>c</sub></td><td style="font-size:25px; font-weight:bold; text-align:center;">=</td><td>
            <table align="center" border="0" cellspacing="0" cellpadding="0"><tr><td style="text-align:center; font-size:18px; padding-bottom:2px;">M ⋅ ΔP</td></tr><tr><td style="border-top: 2px solid white; text-align:center; font-size:18px; padding-top:2px;">&#961; ⋅ B<sub>eff</sub></td></tr></table>
            </td></tr></table></body></html>""")
        Sc_explanation = QLabel("<b>Compressor Power (S<sub>c</sub>):</b><br>Represents the power required for a booster station, based on flow rate (M), total pressure drop over 150 km segment (ΔP = Δp/L × 150,000 m), fluid density (ρ), and booster efficiency (B<sub>eff</sub> = 0.75).")
        Sc_explanation.setWordWrap(True)
        grid_layout.addWidget(Sc_formula_label, 3, 0, Qt.AlignCenter)
        grid_layout.addWidget(Sc_explanation, 3, 1)

        Ib_formula_label = QLabel("""
            <html><body><p align="center" style="font-size:25px; font-weight:bold;">
            I<sub>B</sub> = 0.547 ⋅ S<sub>c</sub> + 0.42</p></body></html>""")
        Ib_explanation = QLabel("<b>Booster Station Cost (I<sub>B</sub>):</b><br>The investment cost for a booster station, calculated as a function of the required compressor power (S<sub>c</sub>).")
        Ib_explanation.setWordWrap(True)
        grid_layout.addWidget(Ib_formula_label, 4, 0, Qt.AlignCenter)
        grid_layout.addWidget(Ib_explanation, 4, 1)

        Itotal_formula_label = QLabel("""
            <html><body><p align="center" style="font-size:25px; font-weight:bold;">
            I<sub>total</sub> = ΣI<sub>p</sub> + ΣI<sub>B</sub></p></body></html>""")
        Itotal_explanation = QLabel("<b>Total Pipeline Cost (I<sub>total</sub>):</b><br>The final cost, calculated as the sum of all pipeline segment costs (ΣI<sub>p</sub>) and all booster station costs (ΣI<sub>B</sub>).")
        Itotal_explanation.setWordWrap(True)
        grid_layout.addWidget(Itotal_formula_label, 5, 0, Qt.AlignCenter)
        grid_layout.addWidget(Itotal_explanation, 5, 1)

        self.setLayout(grid_layout)
