from typing import TYPE_CHECKING
import numpy as np
import os
from PyQt5.QtWidgets import (
    QLabel, QComboBox, QLineEdit, QPushButton, QHBoxLayout, QFormLayout,
    QGroupBox, QVBoxLayout, QDialog, QGridLayout, QRadioButton, QButtonGroup,
    QScrollArea, QWidget
)
from PyQt5.QtCore import Qt
from qgis.core import QgsProject, QgsRaster, QgsPointXY, QgsGeometry
from qgis import processing
from osgeo import gdal

from ..task_manager import run_in_background
from ..utils import update_pipeline_length, update_resolution_field

if TYPE_CHECKING:
    from ..analysis_dialog import AnalysisDialog


def _make_group_box(title_html: str, form_layout: QFormLayout) -> QGroupBox:
    """Helper: wrap a QFormLayout in a styled QGroupBox with a centred bold title."""
    box = QGroupBox()
    box.setStyleSheet("QGroupBox { border: 1px solid grey; }")
    title = QLabel(title_html)
    title.setAlignment(Qt.AlignCenter)
    title.setStyleSheet("font-weight: bold; font-size: 12px;")
    form_layout.insertRow(0, title)
    box.setLayout(form_layout)
    return box


def setup_price_estimation_tab(dialog: 'AnalysisDialog', layout: QVBoxLayout):
    """Sets up the UI for the Price Estimation tab."""
    main_layout = QVBoxLayout()
    columns_layout = QHBoxLayout()
    left_layout = QVBoxLayout()
    right_layout = QVBoxLayout()
    columns_layout.addLayout(left_layout, 1)
    columns_layout.addLayout(right_layout, 1)

    # Description block — scrollable, fixed max height
    descriptionLabel = QLabel("""
        <html>
            <body>
                <p style="text-align:justify; font-size:13px; color:lightgrey; line-height:1.6;">
                    ⓘ This submenu estimates the total pipeline investment cost (<b>I<sub>total</sub></b>) based on the selected pipeline vector and cost rasters. <br><br>
                    The pipeline <b>diameter (D)</b> is calculated once using the full pipeline length and the Darcy-Weisbach equation — it is constant along the entire pipeline. <br><br>
                    The <b>segment length</b> is derived from the pressure budget — total pressure drop ÷ admissible pressure drop (150 km by default). <br><br>
                    If the pipeline is <b>shorter than one segment</b>, a single segment cost <b>I<sub>p</sub></b> is calculated.
                    If longer, the pipeline is split into <b>segments of that length</b>, each with its own <b>I<sub>p</sub></b>,
                    and a <b>booster station (I<sub>B</sub>)</b> is added between each pair of consecutive segments. <br><br>
                    <b>Precise mode</b> resamples all cost rasters to a common resolution and iterates over every GIS cell crossed by the pipeline —
                    cost factor values are read from each cell, and
                    <b>L<sub>cell</sub></b> is the exact pipeline length inside that cell, computed by geometric intersection. <br><br>
                    <b>Fast mode</b> iterates over vector segments (vertex-to-vertex, i.e. the straight line between two consecutive vertices of the pipeline geometry) —
                    5 equally-spaced positions are sampled along each segment on the original rasters (no resampling), and the <b>maximum value</b> found is used as the cost factor.
                    <b>L<sub>seg</sub></b> is the full length of that segment.
                </p>
            </body>
        </html>
    """)
    descriptionLabel.setWordWrap(True)

    descriptionScrollArea = QScrollArea()
    descriptionScrollArea.setWidget(descriptionLabel)
    descriptionScrollArea.setWidgetResizable(True)
    descriptionScrollArea.setMaximumHeight(160)
    descriptionScrollArea.setMinimumHeight(60)
    descriptionScrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    descriptionScrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    descriptionScrollArea.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
    main_layout.addWidget(descriptionScrollArea)

    dialog.show_formulas_button = QPushButton("Show Calculation Formulas")
    main_layout.addWidget(dialog.show_formulas_button)

    main_layout.addLayout(columns_layout)

    # ─── LEFT COLUMN ────────────────────────────────────────────────────────────

    # Select Cost Rasters and Vector
    selectionLayout = QFormLayout()
    dialog.pipelineVectorDropdown = QComboBox()
    dialog.landUseCostsDropdown = QComboBox()
    dialog.slopeCostsDropdown = QComboBox()
    dialog.corridorsCostsDropdown = QComboBox()
    dialog.crossingsCostsDropdown = QComboBox()
    dialog.crossingsVectorDropdown = QComboBox()
    selectionLayout.addRow(QLabel("Pipeline Vector:"), dialog.pipelineVectorDropdown)
    selectionLayout.addRow(QLabel("Land Use Costs Raster (F<sub>lu</sub>):"), dialog.landUseCostsDropdown)
    selectionLayout.addRow(QLabel("Slope Costs Raster (F<sub>s</sub>):"), dialog.slopeCostsDropdown)
    selectionLayout.addRow(QLabel("Corridors Costs Raster (F<sub>c</sub>):"), dialog.corridorsCostsDropdown)
    selectionLayout.addRow(QLabel("Crossings Costs Raster (F<sub>ci</sub>):"), dialog.crossingsCostsDropdown)
    selectionLayout.addRow(QLabel("Infrastructure Vector (for N):"), dialog.crossingsVectorDropdown)
    left_layout.addWidget(_make_group_box("Select Cost Rasters and Vector", selectionLayout))

    # Cost Rasters Resolutions (read-only)
    resolutionsLayout = QFormLayout()
    dialog.landUseCostsResInput = QLineEdit()
    dialog.slopeCostsResInput = QLineEdit()
    dialog.corridorsCostsResInput = QLineEdit()
    dialog.crossingsCostsResInput = QLineEdit()
    for inp in (dialog.landUseCostsResInput, dialog.slopeCostsResInput,
                dialog.corridorsCostsResInput, dialog.crossingsCostsResInput):
        inp.setReadOnly(True)
    resolutionsLayout.addRow(QLabel("Land Use (F<sub>lu</sub>):"), dialog.landUseCostsResInput)
    resolutionsLayout.addRow(QLabel("Slope (F<sub>s</sub>):"), dialog.slopeCostsResInput)
    resolutionsLayout.addRow(QLabel("Corridors (F<sub>c</sub>):"), dialog.corridorsCostsResInput)
    resolutionsLayout.addRow(QLabel("Crossings (F<sub>ci</sub>):"), dialog.crossingsCostsResInput)
    left_layout.addWidget(_make_group_box("Cost Rasters Resolutions", resolutionsLayout))

    # Derived inputs (read-only — auto-calculated from selected vector / pressure inputs)
    derivedLayout = QFormLayout()
    dialog.pipelineLengthInput = QLineEdit()
    dialog.pipelineLengthInput.setReadOnly(True)
    dialog.segmentLengthInput = QLineEdit()
    dialog.segmentLengthInput.setReadOnly(True)
    derivedLayout.addRow(QLabel("Pipeline Length (L, m):"), dialog.pipelineLengthInput)
    derivedLayout.addRow(QLabel("Segment Length (km):"), dialog.segmentLengthInput)
    left_layout.addWidget(_make_group_box("Derived (auto-calculated)", derivedLayout))

    left_layout.addStretch(1)

    # ─── RIGHT COLUMN ───────────────────────────────────────────────────────────

    # Pipe Diameter (D) inputs — Darcy-Weisbach: D = (8λM² / π²ρ(Δp/L))^(1/5)
    dLayout = QFormLayout()
    dialog.frictionFactorInput = QLineEdit()
    dialog.co2MassFlowRateInput = QLineEdit()
    dialog.co2densityInput = QLineEdit()
    dialog.pressureDropInput = QLineEdit()
    dialog.totalPressureDropInput = QLineEdit()
    dialog.frictionFactorInput.setText("0.015")
    dialog.co2MassFlowRateInput.setText("1")
    dialog.co2densityInput.setText("827")
    dialog.pressureDropInput.setText("0.02")
    dialog.totalPressureDropInput.setText("3")
    dLayout.addRow(QLabel("Friction Factor (λ):"), dialog.frictionFactorInput)
    dLayout.addRow(QLabel("CO₂ Mass Flow Rate (M, kg/s):"), dialog.co2MassFlowRateInput)
    dLayout.addRow(QLabel("CO₂ Density (ρ, kg/m³):"), dialog.co2densityInput)
    dLayout.addRow(QLabel("Admissible Pressure Drop (Δp/L, MPa/km):"), dialog.pressureDropInput)
    dLayout.addRow(QLabel("Total Pressure Drop (Δp, MPa):"), dialog.totalPressureDropInput)
    right_layout.addWidget(_make_group_box("Pipe Diameter (D)", dLayout))

    # Segment cost (Ip) inputs — Ip = Bc · D · Σ(Ccell · Lcell)
    ipLayout = QFormLayout()
    dialog.standardizedCostFactorInput = QLineEdit()
    dialog.standardizedCostFactorInput.setText("1357")
    ipLayout.addRow(QLabel("Standardised Cost Factor (B<sub>c</sub>, €/m²):"), dialog.standardizedCostFactorInput)
    right_layout.addWidget(_make_group_box("Segment Cost (I<sub>p</sub>)", ipLayout))

    # Booster stations (Sc, IB) inputs
    boosterLayout = QFormLayout()
    dialog.boosterEfficiencyInput = QLineEdit()
    dialog.boosterVariableCostInput = QLineEdit()
    dialog.boosterFixedCostInput = QLineEdit()
    dialog.boosterEfficiencyInput.setText("0.75")
    dialog.boosterVariableCostInput.setText("0.547")
    dialog.boosterFixedCostInput.setText("0.42")
    boosterLayout.addRow(QLabel("Booster Efficiency (B<sub>eff</sub>):"), dialog.boosterEfficiencyInput)
    boosterLayout.addRow(QLabel("Variable Cost (α, M€/MW):"), dialog.boosterVariableCostInput)
    boosterLayout.addRow(QLabel("Fixed Cost (β, M€):"), dialog.boosterFixedCostInput)
    right_layout.addWidget(_make_group_box("Booster Stations (S<sub>c</sub>, I<sub>B</sub>)", boosterLayout))

    # Populate the derived segment-length field with its initial value
    update_segment_length(dialog)

    # Calculation Mode
    calcModeLayout = QFormLayout()
    dialog.calcModePreciseRadio = QRadioButton("Precise (Cell-based with resampling)")
    dialog.calcModeFastRadio = QRadioButton("Fast (Segment-based with point sampling)")
    dialog.calcModePreciseRadio.setChecked(True)
    dialog.calcModePreciseRadio.setToolTip(
        "Resamples all rasters to common resolution, calculates exact length (L) and crossings (N) per cell.\n"
        "More accurate but slower for large datasets."
    )
    dialog.calcModeFastRadio.setToolTip(
        "Samples 5 points along each vector segment, uses maximum values.\n"
        "Faster but less spatially accurate."
    )
    dialog.calcModeButtonGroup = QButtonGroup()
    dialog.calcModeButtonGroup.addButton(dialog.calcModePreciseRadio)
    dialog.calcModeButtonGroup.addButton(dialog.calcModeFastRadio)
    calcModeLayout.addRow(dialog.calcModePreciseRadio)
    calcModeLayout.addRow(dialog.calcModeFastRadio)
    right_layout.addWidget(_make_group_box("Calculation Mode", calcModeLayout))

    right_layout.addStretch(1)

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

    # Recompute the derived segment length whenever either pressure input changes
    dialog.pressureDropInput.textChanged.connect(lambda: update_segment_length(dialog))
    dialog.totalPressureDropInput.textChanged.connect(lambda: update_segment_length(dialog))


def update_segment_length(dialog: 'AnalysisDialog'):
    """Recomputes the read-only segment length (km) = total pressure drop / admissible pressure drop."""
    try:
        admissible = float(dialog.pressureDropInput.text())  # MPa/km
        total = float(dialog.totalPressureDropInput.text())  # MPa
        if admissible > 0:
            dialog.segmentLengthInput.setText(f"{total / admissible:.2f}")
        else:
            dialog.segmentLengthInput.setText("—")
    except (ValueError, ZeroDivisionError):
        dialog.segmentLengthInput.setText("—")


def run_price_estimation(dialog: 'AnalysisDialog'):
    """Calculates the total pipeline price based on various cost factors."""
    try:
        dialog.log_message("Calculating pipeline price...", "Price Estimation")

        pipeline_layer = QgsProject.instance().mapLayer(dialog.pipelineVectorDropdown.currentData())
        if not pipeline_layer:
            raise ValueError("Pipeline vector must be selected.")

        land_use_layer = QgsProject.instance().mapLayer(dialog.landUseCostsDropdown.currentData())
        slope_layer = QgsProject.instance().mapLayer(dialog.slopeCostsDropdown.currentData())
        corridors_layer = QgsProject.instance().mapLayer(dialog.corridorsCostsDropdown.currentData())
        crossings_layer = QgsProject.instance().mapLayer(dialog.crossingsCostsDropdown.currentData())

        # Log warnings for missing rasters (will default to 1.0)
        for name, layer in [("Land Use (Flu)", land_use_layer), ("Slope (Fs)", slope_layer),
                            ("Corridors (Fc)", corridors_layer), ("Crossings (Fci)", crossings_layer)]:
            if not layer:
                dialog.log_message(f"  ⚠️ {name}: Not selected — will use constant 1.0 (neutral)", "Price Estimation")

        # Choose calculation method based on radio button selection
        use_precise = dialog.calcModePreciseRadio.isChecked()
        if use_precise:
            dialog.log_message("Calculation mode: Precise (Cell-based with resampling)", "Price Estimation")
            full_raster_values = extract_raster_values_along_pipeline_cells(
                dialog, pipeline_layer, land_use_layer, slope_layer, corridors_layer, crossings_layer
            )
        else:
            dialog.log_message("Calculation mode: Fast (Segment-based with point sampling)", "Price Estimation")
            crossings_vector_layer = QgsProject.instance().mapLayer(dialog.crossingsVectorDropdown.currentData())
            if not crossings_vector_layer:
                dialog.log_message("  ⚠️ Infrastructure Vector (for N): Not selected — N will be 1 for all segments (neutral, preserves Fci contribution)", "Price Estimation")
            full_raster_values = extract_raster_values_along_pipeline(
                dialog, pipeline_layer, land_use_layer, slope_layer, corridors_layer, crossings_layer, crossings_vector_layer
            )
        if not full_raster_values:
            raise ValueError("No valid raster values found for the pipeline path. Check if the pipeline intersects with the cost rasters.")

        λ = float(dialog.frictionFactorInput.text())
        M = float(dialog.co2MassFlowRateInput.text())
        p = float(dialog.co2densityInput.text())
        Δp_Ltotal = float(dialog.pressureDropInput.text()) * 1000  # MPa/km → Pa/m (pressure drop per meter)
        total_pressure_drop = float(dialog.totalPressureDropInput.text())  # MPa (max drop per segment)
        Bc = float(dialog.standardizedCostFactorInput.text())

        # Max segment length is derived from the pressure budget:
        # segment (km) = total pressure drop (MPa) / admissible pressure drop (MPa/km)
        admissible_MPa_km = float(dialog.pressureDropInput.text())
        if admissible_MPa_km <= 0:
            raise ValueError("Admissible Pressure Drop must be greater than zero.")
        max_segment_length = (total_pressure_drop / admissible_MPa_km) * 1000  # km → m
        dialog.log_message(f"Max segment length (booster spacing): {max_segment_length / 1000:.2f} km "
                           f"(= {total_pressure_drop} MPa / {admissible_MPa_km} MPa/km)", "Price Estimation")

        segment_costs = []
        booster_costs = []
        segment_index = 0
        total_length = 0

        current_segment_cells = []
        current_segment_length = 0

        Ltotal = sum(cl for _, _, _, _, _, cl in full_raster_values)

        # Calculate diameter D once for the entire pipeline using total length
        D = ((8 * λ * M**2) / (np.pi**2 * p * Δp_Ltotal))**(1 / 5)
        dialog.log_message(f"Pipeline Diameter (D): {D:.4f} m = {D * 1000:.2f} mm", "Price Estimation")
        dialog.log_message("--------------------------------------------------", "Price Estimation")

        for Fc, Fs, Flu, Fci, N, Lcell in full_raster_values:
            current_segment_cells.append((Fc, Fs, Flu, Fci, N, Lcell))
            total_length += Lcell
            current_segment_length += Lcell

            segment_complete = current_segment_length >= max_segment_length
            final_segment = total_length >= Ltotal

            if segment_complete or final_segment:
                L_segment = current_segment_length

                summation = sum(
                    fc_i * fs_i * (flu_i * (1 - 0.1 * n_i) + 0.1 * n_i * fci_i) * cl_i
                    for fc_i, fs_i, flu_i, fci_i, n_i, cl_i in current_segment_cells
                )

                Ip = Bc * D * summation
                segment_costs.append(Ip)
                dialog.log_message(f"Segment {segment_index + 1}: Length = {L_segment:.2f} m, Cost (Ip) = {Ip:,.2f} €", "Price Estimation")

                if not final_segment:
                    # Booster stations are placed at the end of each full segment.
                    # Pressure drop over a full segment = Δp/L × segment length (= total_pressure_drop)
                    ΔP_booster_segment = Δp_Ltotal * max_segment_length  # Pa (pressure drop over one segment)
                    Beff = float(dialog.boosterEfficiencyInput.text())
                    Sc_W = (M * ΔP_booster_segment) / (p * Beff)  # W (compressor power)
                    Sc_MW = Sc_W / 1e6  # converted to MW
                    α = float(dialog.boosterVariableCostInput.text())  # M€/MW (COMET default: 0.547)
                    β = float(dialog.boosterFixedCostInput.text())     # M€ fixed cost (COMET default: 0.42)
                    Ib = (α * Sc_MW + β) * 1e6  # Convert M€ to €
                    booster_costs.append(Ib)
                    dialog.log_message(f"Booster Station after {max_segment_length / 1000:.2f} km: ΔP_segment = {ΔP_booster_segment / 1e6:.2f} MPa, Sc = {Sc_MW:.2f} MW, Cost (Ib) = {Ib:,.2f} €", "Price Estimation")

                current_segment_cells = []
                current_segment_length = 0
                segment_index += 1

        I_total = sum(segment_costs) + sum(booster_costs)
        dialog.log_message("--------------------------------------------------", "Price Estimation")
        dialog.log_message(f"Pipeline Diameter (D): {D:.4f} m = {D * 1000:.2f} mm", "Price Estimation")
        dialog.log_message(f"Calculated Total Pipeline Price (Itotal): {I_total:,.2f} €", "Price Estimation")
        dialog.log_message("--------------------------------------------------", "Price Estimation")

    except Exception as e:
        dialog.log_message(f"Price Estimation Failed: {str(e)}", "Price Estimation")


def extract_raster_values_along_pipeline_cells(dialog, pipeline_layer, land_use_layer, slope_layer, corridors_layer, crossings_layer):
    """
    Extracts raster values along the pipeline using cell-based approach with resampling.
    Uses geometric intersection to calculate precise length within each cell.
    N is calculated by counting pipeline intersections with infrastructure vector within each cell.

    Returns: List of (Fc, Fs, Flu, Fci, N, cell_length) tuples grouped by cell
    """
    import tempfile
    from qgis.core import QgsRectangle

    dialog.log_message("Step 1: Resampling all cost rasters to common resolution...", "Price Estimation")

    # Separate valid from missing layers
    all_input = [
        (land_use_layer, 'Land Use (Flu)'),
        (slope_layer, 'Slope (Fs)'),
        (corridors_layer, 'Corridors (Fc)'),
        (crossings_layer, 'Crossings (Fci)'),
    ]
    valid_layers = [(lyr, n) for lyr, n in all_input if lyr and lyr.isValid()]

    if not valid_layers:
        raise ValueError("At least one cost raster must be provided.")

    # Calculate common extent from valid layers only
    common_extent = valid_layers[0][0].extent()
    for layer, _ in valid_layers[1:]:
        common_extent = common_extent.intersect(layer.extent())

    if common_extent.isEmpty():
        raise ValueError("No common extent found - cost rasters do not overlap!")

    # Use first valid layer as reference for resolution
    reference_layer = valid_layers[0][0]
    ref_resolution = reference_layer.rasterUnitsPerPixelX()

    dialog.log_message(f"  Reference resolution: {ref_resolution:.2f}m from {reference_layer.name()}", "Price Estimation")

    # Resample valid rasters only
    temp_dir = tempfile.mkdtemp()
    resampled_data = {}

    for layer, name in valid_layers:
        resampled_path = os.path.join(temp_dir, f'_price_est_{name.replace(" ", "_")}.tif')

        params = {
            'INPUT': layer,
            'SOURCE_CRS': layer.crs(),
            'TARGET_CRS': reference_layer.crs(),
            'RESAMPLING': 0,  # Nearest neighbor
            'NODATA': None,
            'TARGET_RESOLUTION': ref_resolution,
            'TARGET_EXTENT': f"{common_extent.xMinimum()},{common_extent.xMaximum()},{common_extent.yMinimum()},{common_extent.yMaximum()}",
            'OUTPUT': resampled_path,
            'EXTRA': '-co COMPRESS=LZW -co BIGTIFF=YES'
        }

        result = processing.run('gdal:warpreproject', params)

        if result and 'OUTPUT' in result:
            ds = gdal.Open(result['OUTPUT'])
            data = ds.GetRasterBand(1).ReadAsArray().astype(np.float32)

            # Store metadata from first raster
            if not resampled_data:
                width = ds.RasterXSize
                height = ds.RasterYSize
                geotrans = ds.GetGeoTransform()
                resampled_data['_meta'] = {'width': width, 'height': height, 'geotrans': geotrans}

            resampled_data[name] = data
            ds = None
            dialog.log_message(f"  ✓ Resampled {name}", "Price Estimation")
        else:
            raise RuntimeError(f"Failed to resample {layer.name()}")

    # Get dimensions
    meta = resampled_data['_meta']
    width, height = meta['width'], meta['height']
    geotrans = meta['geotrans']
    cell_width = abs(geotrans[1])
    cell_height = abs(geotrans[5])
    origin_x = geotrans[0]
    origin_y = geotrans[3]

    dialog.log_message(f"  Resampled grid: {width}x{height} cells, cell size: {cell_width:.2f}m x {cell_height:.2f}m", "Price Estimation")

    # Create arrays — missing rasters default to 1.0 (neutral)
    Flu = resampled_data.get('Land Use (Flu)', np.ones((height, width), dtype=np.float32))
    Fs = resampled_data.get('Slope (Fs)', np.ones((height, width), dtype=np.float32))
    Fc = resampled_data.get('Corridors (Fc)', np.ones((height, width), dtype=np.float32))
    Fci = resampled_data.get('Crossings (Fci)', np.ones((height, width), dtype=np.float32))

    for name, key in [("Land Use (Flu)", 'Land Use (Flu)'), ("Slope (Fs)", 'Slope (Fs)'),
                      ("Corridors (Fc)", 'Corridors (Fc)'), ("Crossings (Fci)", 'Crossings (Fci)')]:
        if key not in resampled_data:
            dialog.log_message(f"  ⚠️ {name}: Not selected — assuming constant 1.0 (neutral)", "Price Estimation")

    dialog.log_message("Step 2: Extracting pipeline segments and calculating cell intersections...", "Price Estimation")

    # Get infrastructure vector for N calculation
    crossings_vector_layer = QgsProject.instance().mapLayer(dialog.crossingsVectorDropdown.currentData()) if hasattr(dialog, 'crossingsVectorDropdown') else None

    if not crossings_vector_layer:
        dialog.log_message("  ⚠️ No infrastructure vector selected - N will be 1 for all cells (neutral, preserves Fci contribution)", "Price Estimation")
        infrastructure_features = []
    else:
        infrastructure_features = list(crossings_vector_layer.getFeatures())
        dialog.log_message(f"  Loaded {len(infrastructure_features)} infrastructure features for N calculation", "Price Estimation")

    # PRE-PASS: Quick count of total unique cells (fast, no heavy geometry operations)
    dialog.log_message("  Counting total unique cells...", "Price Estimation")
    unique_cells_set = set()
    for feature in pipeline_layer.getFeatures():
        geom = feature.geometry()
        parts = geom.asMultiPolyline() if geom.isMultipart() else [geom.asPolyline()]
        for line in parts:
            for i in range(len(line) - 1):
                start, end = line[i], line[i + 1]
                cells_touched = get_intersected_cells(
                    start.x(), start.y(), end.x(), end.y(),
                    origin_x, origin_y,
                    cell_width, cell_height,
                    width, height
                )
                unique_cells_set.update(cells_touched)

    total_unique_cells = len(unique_cells_set)
    dialog.log_message(f"  Found {total_unique_cells} unique cells to process", "Price Estimation")

    # Dictionary to accumulate data per cell: {(row, col): {'Fc': val, 'Fs': val, ..., 'L': total_length, 'N': count}}
    cell_data = {}

    total_segments = 0
    processed_cells = 0

    # Process pipeline segments
    for feature in pipeline_layer.getFeatures():
        geom = feature.geometry()
        parts = geom.asMultiPolyline() if geom.isMultipart() else [geom.asPolyline()]

        for line in parts:
            for i in range(len(line) - 1):
                start, end = line[i], line[i + 1]
                total_segments += 1

                # Create segment geometry
                segment_geom = QgsGeometry.fromPolylineXY([start, end])

                # Get cells intersected by this segment
                cells_touched = get_intersected_cells(
                    start.x(), start.y(), end.x(), end.y(),
                    origin_x, origin_y,
                    cell_width, cell_height,
                    width, height
                )

                # For each cell touched by this segment
                for col, row in cells_touched:
                    # Create cell polygon
                    cell_x_min = origin_x + col * cell_width
                    cell_x_max = cell_x_min + cell_width
                    cell_y_max = origin_y - row * cell_height
                    cell_y_min = cell_y_max - cell_height

                    cell_rect = QgsRectangle(cell_x_min, cell_y_min, cell_x_max, cell_y_max)
                    cell_polygon = QgsGeometry.fromRect(cell_rect)

                    # Calculate intersection length (Lcell)
                    intersection = segment_geom.intersection(cell_polygon)
                    if intersection.isEmpty():
                        continue

                    length_in_cell = intersection.length()

                    # Count infrastructure intersections within this cell (N)
                    n_in_cell = 0
                    for infra_feature in infrastructure_features:
                        infra_geom = infra_feature.geometry()
                        # Check if infrastructure intersects both the segment AND the cell
                        if segment_geom.intersects(infra_geom):
                            # Further check if intersection happens within this specific cell
                            infra_in_cell = infra_geom.intersection(cell_polygon)
                            if not infra_in_cell.isEmpty() and segment_geom.intersects(infra_in_cell):
                                n_in_cell += 1

                    # Initialize cell data if first time
                    cell_key = (row, col)
                    is_new_cell = cell_key not in cell_data
                    if is_new_cell:
                        cell_data[cell_key] = {
                            'Fc': float(Fc[row, col]),
                            'Fs': float(Fs[row, col]),
                            'Flu': float(Flu[row, col]),
                            'Fci': float(Fci[row, col]),
                            'L': 0.0,
                            'N': 0
                        }
                        processed_cells += 1

                        # Log every single unique cell processed with total
                        dialog.log_message(f"  Processing unique cell {processed_cells}/{total_unique_cells} (row={row}, col={col})", "Price Estimation")

                    # Accumulate length and N
                    cell_data[cell_key]['L'] += length_in_cell
                    cell_data[cell_key]['N'] += n_in_cell

    dialog.log_message(f"  Processed {total_segments} segments across {len(cell_data)} unique cells", "Price Estimation")

    # Convert dictionary to list of tuples
    values = []
    for (row, col), data in cell_data.items():
        # If no infrastructure vector was provided, N defaults to 1 (preserves Fci contribution)
        # Cap N at 10 (same as LCP)
        n_capped = min(max(data['N'], 1 if not infrastructure_features else 0), 10)
        values.append((
            data['Fc'],
            data['Fs'],
            data['Flu'],
            data['Fci'],
            n_capped,
            data['L']
        ))

    dialog.log_message(f"  ✓ Extracted {len(values)} cell entries with total length: {sum(v[5] for v in values):.2f}m", "Price Estimation")

    # Cleanup temp files
    try:
        import shutil
        shutil.rmtree(temp_dir)
    except BaseException:
        pass

    return values


def get_intersected_cells(x1, y1, x2, y2, origin_x, origin_y, cell_width, cell_height, grid_width, grid_height):
    """
    Get all raster cells intersected by a line segment using a rasterization algorithm.

    Parameters:
        x1, y1, x2, y2: Line segment endpoints in map coordinates
        origin_x, origin_y: Top-left corner of raster (origin_y is top)
        cell_width, cell_height: Cell dimensions
        grid_width, grid_height: Raster dimensions in cells

    Returns:
        List of (col, row) tuples
    """
    cells = set()

    # Convert endpoints to cell coordinates
    col1 = int((x1 - origin_x) / cell_width)
    row1 = int((origin_y - y1) / cell_height)
    col2 = int((x2 - origin_x) / cell_width)
    row2 = int((origin_y - y2) / cell_height)

    # Bresenham's line algorithm (adapted for cells)
    dx = abs(col2 - col1)
    dy = abs(row2 - row1)

    col = col1
    row = row1

    col_inc = 1 if col2 > col1 else -1
    row_inc = 1 if row2 > row1 else -1

    # Add cells along the line
    if dx > dy:
        error = dx / 2
        while col != col2:
            if 0 <= col < grid_width and 0 <= row < grid_height:
                cells.add((col, row))
            error -= dy
            if error < 0:
                row += row_inc
                error += dx
            col += col_inc
    else:
        error = dy / 2
        while row != row2:
            if 0 <= col < grid_width and 0 <= row < grid_height:
                cells.add((col, row))
            error -= dx
            if error < 0:
                col += col_inc
                error += dy
            row += row_inc

    # Add final cell
    if 0 <= col2 < grid_width and 0 <= row2 < grid_height:
        cells.add((col2, row2))

    return list(cells)


def extract_raster_values_along_pipeline(dialog, pipeline_layer, land_use_layer, slope_layer, corridors_layer, crossings_layer, crossings_vector_layer):
    """
    Extracts raster values at multiple points along each segment of the pipeline, returning the maximum value for each raster.
    Missing rasters default to 1.0 (neutral). Missing infrastructure vector defaults to N=0.
    """
    values = []

    # Log warnings for missing inputs
    for name, layer in [("Land Use (Flu)", land_use_layer), ("Slope (Fs)", slope_layer),
                        ("Corridors (Fc)", corridors_layer), ("Crossings (Fci)", crossings_layer)]:
        if not layer:
            dialog.log_message(f"  ⚠️ {name}: Not selected — assuming constant 1.0 (neutral)", "Price Estimation")

    crossings_features = list(crossings_vector_layer.getFeatures()) if crossings_vector_layer else []

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
                # Default N to 1 if no infrastructure vector provided (preserves Fci contribution)
                if not crossings_features:
                    num_intersections = 1

                cell_length = start.distance(end)
                sample_ratios = [0.0, 0.25, 0.5, 0.75, 1.0]
                corridors_vals, land_use_vals, slope_vals, crossings_vals = [], [], [], []

                for ratio in sample_ratios:
                    x = start.x() + (end.x() - start.x()) * ratio
                    y = start.y() + (end.y() - start.y()) * ratio
                    point = QgsPointXY(x, y)

                    Fc = get_raster_value_at_point(corridors_layer, point)
                    Fs = get_raster_value_at_point(slope_layer, point)
                    Flu = get_raster_value_at_point(land_use_layer, point)
                    Fci = get_raster_value_at_point(crossings_layer, point)

                    corridors_vals.append(Fc if Fc is not None else 1.0)
                    slope_vals.append(Fs if Fs is not None else 1.0)
                    land_use_vals.append(Flu if Flu is not None else 1.0)
                    crossings_vals.append(Fci if Fci is not None else 1.0)

                values.append((
                    max(corridors_vals),
                    max(slope_vals),
                    max(land_use_vals),
                    max(crossings_vals),
                    num_intersections,
                    cell_length
                ))
    return values


def get_raster_value_at_point(raster_layer, point):
    """Gets a raster value at a specific point."""
    if not raster_layer:
        return None
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
        self.setMinimumSize(800, 500)
        self.resize(1000, 700)
        self.setSizeGripEnabled(True)
        self.setStyleSheet("""
            QDialog { background-color: #2a2a2a; }
            QLabel { color: white; font-size: 13px; }
            QScrollArea { background-color: #2a2a2a; border: none; }
            QWidget#scrollContent { background-color: #2a2a2a; }
        """)

        # Inner widget that holds the grid
        scroll_content = QWidget()
        scroll_content.setObjectName("scrollContent")

        grid_layout = QGridLayout(scroll_content)
        grid_layout.setSpacing(24)
        grid_layout.setContentsMargins(20, 20, 20, 20)
        grid_layout.setColumnStretch(0, 3)
        grid_layout.setColumnStretch(1, 2)

        # --- D ---
        D_formula_label = QLabel("""
            <html><body><table align="center" border="0" cellspacing="0" cellpadding="5">
            <tr>
              <td style="font-size:28px; font-weight:bold;">D</td>
              <td style="font-size:28px; font-weight:bold; padding:0 8px;">=</td>
              <td style="font-size:48px; font-weight:bold;">(</td>
              <td>
                <table align="center" border="0" cellspacing="0" cellpadding="0">
                  <tr><td style="text-align:center; font-size:20px; padding-bottom:4px;">8 ⋅ λ ⋅ M²</td></tr>
                  <tr><td style="border-top: 2px solid white; text-align:center; font-size:20px; padding-top:4px;">π² ⋅ ρ ⋅ (Δp/L)</td></tr>
                </table>
              </td>
              <td style="font-size:48px; font-weight:bold;">)</td>
              <td style="font-size:24px; font-weight:bold; vertical-align:top; padding-top:4px;"><sup>1/5</sup></td>
            </tr></table></body></html>""")
        D_explanation = QLabel(
            "<b>Pipeline Diameter (D):</b><br><br>"
            "Calculated <b>once</b> for the entire pipeline using the Darcy-Weisbach equation. "
            "D is <b>constant</b> along the full pipeline — it does not vary between segments or cells.<br><br>"
            "<b>λ</b> = Darcy friction factor &nbsp;|&nbsp; <b>M</b> = CO₂ mass flow rate (kg/s)<br>"
            "<b>ρ</b> = CO₂ density (kg/m³)<br>"
            "<b>Δp/L</b> = admissible pressure drop per unit length (Pa/m)"
        )
        D_explanation.setWordWrap(True)
        grid_layout.addWidget(D_formula_label, 0, 0, Qt.AlignCenter)
        grid_layout.addWidget(D_explanation, 0, 1)

        # --- Ip ---
        Ip_formula_label = QLabel("""
            <html><body><p align="center" style="font-size:20px; font-weight:bold; line-height:1.8;">
            I<sub>p</sub> = B<sub>c</sub> ⋅ D ⋅ Σ { F<sub>c</sub> ⋅ F<sub>s</sub> ⋅ [F<sub>lu</sub> ⋅ (1 − 0.1N) + 0.1N ⋅ F<sub>ci</sub>] ⋅ <span style="color:#7ec8e3;">L</span> }
            </p>
            <p align="center" style="font-size:16px; color:#aaaaaa;">
            <span style="color:#7ec8e3;">L</span> = L<sub>cell</sub> (Precise mode) &nbsp;|&nbsp; L<sub>seg</sub> (Fast mode)
            </p></body></html>""")
        Ip_explanation = QLabel(
            "<b>Pipeline Segment Cost (I<sub>p</sub>):</b><br><br>"
            "Cost of one pipeline segment (up to the derived segment length, 150 km by default), applying the COMET multiplicative formula.<br><br>"
            "<b>B<sub>c</sub></b> = standardized base cost (€/m²) &nbsp;|&nbsp; <b>D</b> = diameter (m)<br>"
            "<b>F<sub>c</sub></b> = corridor factor &nbsp;|&nbsp; <b>F<sub>s</sub></b> = slope factor<br>"
            "<b>F<sub>lu</sub></b> = land use factor &nbsp;|&nbsp; <b>F<sub>ci</sub></b> = crossing factor<br>"
            "<b>N</b> = infrastructure crossings (max 10)<br><br>"
            "<b>L depends on the calculation mode:</b><br>"
            "• <b>Precise:</b> <b>L<sub>cell</sub></b> = exact pipeline length inside each GIS raster cell, "
            "computed by geometric intersection of the pipeline vector with each cell polygon. "
            "The summation iterates over all unique cells crossed.<br>"
            "• <b>Fast:</b> <b>L<sub>seg</sub></b> = full length of each vector segment (vertex-to-vertex). "
            "A vector segment is the straight line between two consecutive vertices of the pipeline geometry. "
            "The summation iterates over all vector segments."
        )
        Ip_explanation.setWordWrap(True)
        grid_layout.addWidget(Ip_formula_label, 1, 0, Qt.AlignCenter)
        grid_layout.addWidget(Ip_explanation, 1, 1)

        # --- Sc ---
        Sc_formula_label = QLabel("""
            <html><body><table align="center" border="0" cellspacing="0" cellpadding="5">
            <tr>
              <td style="font-size:28px; font-weight:bold;">S<sub>c</sub></td>
              <td style="font-size:28px; font-weight:bold; padding:0 8px;">=</td>
              <td>
                <table align="center" border="0" cellspacing="0" cellpadding="0">
                  <tr><td style="text-align:center; font-size:20px; padding-bottom:4px;">M ⋅ ΔP<sub>seg</sub></td></tr>
                  <tr><td style="border-top: 2px solid white; text-align:center; font-size:20px; padding-top:4px;">ρ ⋅ B<sub>eff</sub></td></tr>
                </table>
              </td>
            </tr></table></body></html>""")
        Sc_explanation = QLabel(
            "<b>Compressor Power (S<sub>c</sub>):</b><br><br>"
            "Power required for each booster station, placed at the end of every full segment (derived segment length, 150 km by default). "
            "<b>M</b> = CO₂ mass flow rate (kg/s), "
            "<b>ΔP<sub>seg</sub></b> = total pressure drop over one segment = Δp/L × segment length (Pa), "
            "<b>ρ</b> = CO₂ density (kg/m³), "
            "<b>B<sub>eff</sub></b> = booster efficiency (default 0.75, editable in the inputs panel). "
            "Result is in Watts (W)."
        )
        Sc_explanation.setWordWrap(True)
        grid_layout.addWidget(Sc_formula_label, 2, 0, Qt.AlignCenter)
        grid_layout.addWidget(Sc_explanation, 2, 1)

        # --- IB ---
        Ib_formula_label = QLabel("""
            <html><body><p align="center" style="font-size:26px; font-weight:bold; line-height:1.6;">
            I<sub>B</sub> = (α ⋅ S<sub>c</sub>[MW] + β) × 10⁶
            </p></body></html>""")
        Ib_explanation = QLabel(
            "<b>Booster Station Cost (I<sub>B</sub>):</b><br><br>"
            "Investment cost for a booster station in euros (€). "
            "S<sub>c</sub> must be converted to MW before applying the formula. "
            "<b>α</b> (default 0.547 M€/MW) is the variable cost per unit of compressor capacity; "
            "<b>β</b> (default 0.42 M€) is the fixed installation cost regardless of station size. "
            "Both constants originate from COMET TN6.4 (van den Broek et al., 2013) and are editable in the inputs panel."
        )
        Ib_explanation.setWordWrap(True)
        grid_layout.addWidget(Ib_formula_label, 3, 0, Qt.AlignCenter)
        grid_layout.addWidget(Ib_explanation, 3, 1)

        # --- Itotal ---
        Itotal_formula_label = QLabel("""
            <html><body><p align="center" style="font-size:28px; font-weight:bold; line-height:1.6;">
            I<sub>total</sub> = ΣI<sub>p</sub> + ΣI<sub>B</sub>
            </p></body></html>""")
        Itotal_explanation = QLabel(
            "<b>Total Pipeline Cost (I<sub>total</sub>):</b><br><br>"
            "The total investment cost in euros (€), calculated as the sum of all pipeline "
            "segment costs (ΣI<sub>p</sub>) and all booster station costs (ΣI<sub>B</sub>). "
            "For pipelines shorter than one segment there are no booster stations (ΣI<sub>B</sub> = 0). "
            "For longer pipelines, one booster station is added after every full segment."
        )
        Itotal_explanation.setWordWrap(True)
        grid_layout.addWidget(Itotal_formula_label, 4, 0, Qt.AlignCenter)
        grid_layout.addWidget(Itotal_explanation, 4, 1)

        scroll_area = QScrollArea()
        scroll_area.setWidget(scroll_content)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll_area)
        self.setLayout(outer_layout)
