from typing import TYPE_CHECKING

from qgis.core import QgsGeometry
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..constants import capex
from ..core.capex import COST_NAMES, compute_capex, extract_cells, extract_points
from ..task_manager import run_task
from ..utils import get_layer_path, layer_from_dropdown, update_pipeline_length, update_resolution_field
from ..widgets.browse_row import make_group_box

if TYPE_CHECKING:
    from ..analysis_dialog import AnalysisDialog


def setup_price_estimation_tab(dialog: "AnalysisDialog", layout: QVBoxLayout):
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
    descriptionScrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    descriptionScrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
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
    left_layout.addWidget(make_group_box("Select Cost Rasters and Vector", selectionLayout))

    # Cost Rasters Resolutions (read-only)
    resolutionsLayout = QFormLayout()
    dialog.landUseCostsResInput = QLineEdit()
    dialog.slopeCostsResInput = QLineEdit()
    dialog.corridorsCostsResInput = QLineEdit()
    dialog.crossingsCostsResInput = QLineEdit()
    for inp in (
        dialog.landUseCostsResInput,
        dialog.slopeCostsResInput,
        dialog.corridorsCostsResInput,
        dialog.crossingsCostsResInput,
    ):
        inp.setReadOnly(True)
    resolutionsLayout.addRow(QLabel("Land Use (F<sub>lu</sub>):"), dialog.landUseCostsResInput)
    resolutionsLayout.addRow(QLabel("Slope (F<sub>s</sub>):"), dialog.slopeCostsResInput)
    resolutionsLayout.addRow(QLabel("Corridors (F<sub>c</sub>):"), dialog.corridorsCostsResInput)
    resolutionsLayout.addRow(QLabel("Crossings (F<sub>ci</sub>):"), dialog.crossingsCostsResInput)
    left_layout.addWidget(make_group_box("Cost Rasters Resolutions", resolutionsLayout))

    # Derived inputs (read-only — auto-calculated from selected vector / pressure inputs)
    derivedLayout = QFormLayout()
    dialog.pipelineLengthInput = QLineEdit()
    dialog.pipelineLengthInput.setReadOnly(True)
    dialog.segmentLengthInput = QLineEdit()
    dialog.segmentLengthInput.setReadOnly(True)
    derivedLayout.addRow(QLabel("Pipeline Length (L, m):"), dialog.pipelineLengthInput)
    derivedLayout.addRow(QLabel("Segment Length (km):"), dialog.segmentLengthInput)
    left_layout.addWidget(make_group_box("Derived (auto-calculated)", derivedLayout))

    left_layout.addStretch(1)

    # ─── RIGHT COLUMN ───────────────────────────────────────────────────────────

    # Pipe Diameter (D) inputs — Darcy-Weisbach: D = (8λM² / π²ρ(Δp/L))^(1/5)
    dLayout = QFormLayout()
    dialog.frictionFactorInput = QLineEdit()
    dialog.co2MassFlowRateInput = QLineEdit()
    dialog.co2densityInput = QLineEdit()
    dialog.pressureDropInput = QLineEdit()
    dialog.totalPressureDropInput = QLineEdit()
    dialog.frictionFactorInput.setText(str(capex.FRICTION_FACTOR))
    dialog.co2MassFlowRateInput.setText("1")
    dialog.co2densityInput.setText(str(capex.CO2_DENSITY))
    dialog.pressureDropInput.setText("0.02")
    dialog.totalPressureDropInput.setText("3")
    dLayout.addRow(QLabel("Friction Factor (λ):"), dialog.frictionFactorInput)
    dLayout.addRow(QLabel("CO₂ Mass Flow Rate (M, kg/s):"), dialog.co2MassFlowRateInput)
    dLayout.addRow(QLabel("CO₂ Density (ρ, kg/m³):"), dialog.co2densityInput)
    dLayout.addRow(QLabel("Admissible Pressure Drop (Δp/L, MPa/km):"), dialog.pressureDropInput)
    dLayout.addRow(QLabel("Total Pressure Drop (Δp, MPa):"), dialog.totalPressureDropInput)
    right_layout.addWidget(make_group_box("Pipe Diameter (D)", dLayout))

    # Segment cost (Ip) inputs — Ip = Bc · D · Σ(Ccell · Lcell)
    ipLayout = QFormLayout()
    dialog.standardizedCostFactorInput = QLineEdit()
    dialog.standardizedCostFactorInput.setText(str(capex.STANDARDIZED_COST_FACTOR))
    ipLayout.addRow(QLabel("Standardised Cost Factor (B<sub>c</sub>, €/m²):"), dialog.standardizedCostFactorInput)
    right_layout.addWidget(make_group_box("Segment Cost (I<sub>p</sub>)", ipLayout))

    # Booster stations (Sc, IB) inputs
    boosterLayout = QFormLayout()
    dialog.boosterEfficiencyInput = QLineEdit()
    dialog.boosterVariableCostInput = QLineEdit()
    dialog.boosterFixedCostInput = QLineEdit()
    dialog.boosterEfficiencyInput.setText(str(capex.BOOSTER_EFFICIENCY))
    dialog.boosterVariableCostInput.setText(str(capex.BOOSTER_VARIABLE_COST))
    dialog.boosterFixedCostInput.setText(str(capex.BOOSTER_FIXED_COST))
    boosterLayout.addRow(QLabel("Booster Efficiency (B<sub>eff</sub>):"), dialog.boosterEfficiencyInput)
    boosterLayout.addRow(QLabel("Variable Cost (α, M€/MW):"), dialog.boosterVariableCostInput)
    boosterLayout.addRow(QLabel("Fixed Cost (β, M€):"), dialog.boosterFixedCostInput)
    right_layout.addWidget(make_group_box("Booster Stations (S<sub>c</sub>, I<sub>B</sub>)", boosterLayout))

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
        "Samples 5 points along each vector segment, uses maximum values.\nFaster but less spatially accurate."
    )
    dialog.calcModeButtonGroup = QButtonGroup()
    dialog.calcModeButtonGroup.addButton(dialog.calcModePreciseRadio)
    dialog.calcModeButtonGroup.addButton(dialog.calcModeFastRadio)
    calcModeLayout.addRow(dialog.calcModePreciseRadio)
    calcModeLayout.addRow(dialog.calcModeFastRadio)
    right_layout.addWidget(make_group_box("Calculation Mode", calcModeLayout))

    right_layout.addStretch(1)

    dialog.calculatePriceButton = QPushButton("Calculate pipeline price")
    main_layout.addWidget(dialog.calculatePriceButton)

    layout.addLayout(main_layout)


def connect_price_estimation_signals(dialog: "AnalysisDialog"):
    """Connects signals for the Price Estimation tab."""
    dialog.calculatePriceButton.clicked.connect(
        lambda checked: run_task(dialog, "Price Estimation", work=_price_work, prepare=_price_prepare)
    )
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


def update_segment_length(dialog: "AnalysisDialog"):
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


def _price_prepare(dialog: "AnalysisDialog") -> dict:
    """Main thread: read widgets, resolve layers to paths/specs, capture geometry.

    Reads everything ``work`` needs off the dialog (widgets / live project layers
    are only safe here, on the UI thread). Raises ``ValueError`` on bad input.
    """

    def log(msg):
        dialog.log_message(msg, "Price Estimation")

    log("Calculating pipeline price...")

    pipeline_layer = layer_from_dropdown(dialog.pipelineVectorDropdown)
    if not pipeline_layer:
        raise ValueError("Pipeline vector must be selected.")

    cost_dropdowns = {
        "Land Use (Flu)": dialog.landUseCostsDropdown,
        "Slope (Fs)": dialog.slopeCostsDropdown,
        "Corridors (Fc)": dialog.corridorsCostsDropdown,
        "Crossings (Fci)": dialog.crossingsCostsDropdown,
    }

    # Resolve cost rasters: full spec (precise) + plain path (fast). Log warnings
    # for missing rasters (they will default to constant 1.0 in both modes).
    cost_specs = {}
    cost_paths = {}
    for name in COST_NAMES:
        layer = layer_from_dropdown(cost_dropdowns[name])
        if not layer:
            log(f"  ⚠️ {name}: Not selected — will use constant 1.0 (neutral)")
            cost_paths[name] = None
            continue
        cost_paths[name] = get_layer_path(layer)
        if layer.isValid():
            ext = layer.extent()
            cost_specs[name] = {
                "path": get_layer_path(layer),
                "name": layer.name(),
                "crs_wkt": layer.crs().toWkt(),
                "extent": (ext.xMinimum(), ext.xMaximum(), ext.yMinimum(), ext.yMaximum()),
                "res": layer.rasterUnitsPerPixelX(),
            }

    # Calculation mode (precise = cell-based with resampling, fast = point sampling).
    mode = "precise" if dialog.calcModePreciseRadio.isChecked() else "fast"
    if mode == "precise":
        log("Calculation mode: Precise (Cell-based with resampling)")
    else:
        log("Calculation mode: Fast (Segment-based with point sampling)")

    # Infrastructure (crossings) vector → detached geometry copies for N counting. Both backends
    # log the feature count / "not selected" warning themselves (extract_cells / extract_points).
    crossings_layer = layer_from_dropdown(dialog.crossingsVectorDropdown)
    infra_geoms = []
    if crossings_layer:
        for feat in crossings_layer.getFeatures():
            infra_geoms.append(QgsGeometry(feat.geometry()))

    # Capture pipeline segments as plain coordinate pairs on the main thread.
    segments = []
    for feature in pipeline_layer.getFeatures():
        geom = feature.geometry()
        parts = geom.asMultiPolyline() if geom.isMultipart() else [geom.asPolyline()]
        for line in parts:
            for i in range(len(line) - 1):
                start, end = line[i], line[i + 1]
                segments.append((start.x(), start.y(), end.x(), end.y()))

    # Engineering inputs.
    admissible_MPa_km = float(dialog.pressureDropInput.text())  # Δp/L, MPa/km
    if admissible_MPa_km <= 0:
        raise ValueError("Admissible Pressure Drop must be greater than zero.")
    eng = {
        "λ": float(dialog.frictionFactorInput.text()),
        "M": float(dialog.co2MassFlowRateInput.text()),
        "p": float(dialog.co2densityInput.text()),
        "Δp_Ltotal": admissible_MPa_km * 1000,  # MPa/km → Pa/m (pressure drop per meter)
        "total_pressure_drop": float(dialog.totalPressureDropInput.text()),  # MPa (max drop per segment)
        "admissible_MPa_km": admissible_MPa_km,
        "Bc": float(dialog.standardizedCostFactorInput.text()),
        "Beff": float(dialog.boosterEfficiencyInput.text()),
        "α": float(dialog.boosterVariableCostInput.text()),  # M€/MW (COMET default: capex.BOOSTER_VARIABLE_COST)
        "β": float(dialog.boosterFixedCostInput.text()),  # M€ fixed cost (COMET default: capex.BOOSTER_FIXED_COST)
    }

    return {
        "mode": mode,
        "cost_specs": cost_specs,
        "cost_paths": cost_paths,
        "segments": segments,
        "infra_geoms": infra_geoms,
        "eng": eng,
        "log": log,
    }


def _price_work(params: dict) -> dict:
    """Background thread: sample cost factors along the route, then compute CAPEX."""
    log = params["log"]
    if params["mode"] == "precise":
        values = extract_cells(params["cost_specs"], params["segments"], params["infra_geoms"], log)
    else:
        values = extract_points(params["cost_paths"], params["segments"], params["infra_geoms"], log)

    if not values:
        raise ValueError(
            "No valid raster values found for the pipeline path. "
            "Check if the pipeline intersects with the cost rasters."
        )

    return compute_capex(values, params["eng"], log)


def open_formulas_dialog(parent_dialog):
    """Opens the dialog that displays the formulas."""
    dialog = FormulaDialog(parent_dialog)
    dialog.exec()


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
        grid_layout.addWidget(D_formula_label, 0, 0, Qt.AlignmentFlag.AlignCenter)
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
        grid_layout.addWidget(Ip_formula_label, 1, 0, Qt.AlignmentFlag.AlignCenter)
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
            f"<b>B<sub>eff</sub></b> = booster efficiency (default {capex.BOOSTER_EFFICIENCY}, editable in the inputs panel). "
            "Result is in Watts (W)."
        )
        Sc_explanation.setWordWrap(True)
        grid_layout.addWidget(Sc_formula_label, 2, 0, Qt.AlignmentFlag.AlignCenter)
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
            f"<b>α</b> (default {capex.BOOSTER_VARIABLE_COST} M€/MW) is the variable cost per unit of compressor capacity; "
            f"<b>β</b> (default {capex.BOOSTER_FIXED_COST} M€) is the fixed installation cost regardless of station size. "
            "Both constants originate from COMET TN6.4 (van den Broek et al., 2013) and are editable in the inputs panel."
        )
        Ib_explanation.setWordWrap(True)
        grid_layout.addWidget(Ib_formula_label, 3, 0, Qt.AlignmentFlag.AlignCenter)
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
        grid_layout.addWidget(Itotal_formula_label, 4, 0, Qt.AlignmentFlag.AlignCenter)
        grid_layout.addWidget(Itotal_explanation, 4, 1)

        scroll_area = QScrollArea()
        scroll_area.setWidget(scroll_content)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll_area)
        self.setLayout(outer_layout)
