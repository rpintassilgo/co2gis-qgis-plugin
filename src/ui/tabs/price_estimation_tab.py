from typing import TYPE_CHECKING

from qgis.core import QgsGeometry
from qgis.gui import QgsFieldComboBox
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
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ...constants import capex
from ...core.capex import (
    COST_NAMES,
    compute_capex,
    compute_network_capex,
    extract_cells,
    extract_network_values,
    extract_points,
)
from ...task_manager import run_task
from ...utils import get_layer_path, layer_from_dropdown, update_pipeline_length, update_resolution_field
from ...widgets.browse_row import make_group_box

if TYPE_CHECKING:
    from ...analysis_dialog import AnalysisDialog


def setup_price_estimation_tab(dialog: "AnalysisDialog", layout: QVBoxLayout):
    """Sets up the UI for the Price Estimation tab."""
    main_layout = QVBoxLayout()
    columns_layout = QHBoxLayout()
    left_layout = QVBoxLayout()
    right_layout = QVBoxLayout()
    columns_layout.addLayout(left_layout, 1)
    columns_layout.addLayout(right_layout, 1)

    # The intro/help text now lives inside the "info & formulas" dialog (below) to save vertical
    # space — the tab is tight once the Network pickers are shown.
    # Escape the ampersand ("&&") so Qt doesn't treat it as a mnemonic (which underlined the next letter).
    dialog.show_formulas_button = QPushButton("ⓘ  Show info && calculation formulas")
    main_layout.addWidget(dialog.show_formulas_button)

    main_layout.addLayout(columns_layout)

    # ─── LEFT COLUMN ────────────────────────────────────────────────────────────

    # Select Cost Rasters and Vector
    selectionLayout = QFormLayout()
    dialog.pipelineVectorDropdown = QComboBox()
    dialog.priceNetworkVectorDropdown = QComboBox()
    dialog.priceNetworkFlowField = QgsFieldComboBox()
    dialog.landUseCostsDropdown = QComboBox()
    dialog.slopeCostsDropdown = QComboBox()
    dialog.corridorsCostsDropdown = QComboBox()
    dialog.crossingsCostsDropdown = QComboBox()
    dialog.crossingsVectorDropdown = QComboBox()

    # Single vs Network (Network experimental — gated by the Settings toggle). The two vector pickers
    # live in a QStackedWidget: Single = one pipeline (one diameter); Network = a 2a network.gpkg, each
    # segment sized for its own flow with a junction booster where flows merge.
    dialog.priceModeSingleRadio = QRadioButton("Single pipeline")
    dialog.priceModeNetworkRadio = QRadioButton("Network (per-segment flow)")
    dialog.priceModeSingleRadio.setChecked(True)
    dialog.priceModeButtonGroup = QButtonGroup()
    dialog.priceModeButtonGroup.addButton(dialog.priceModeSingleRadio)
    dialog.priceModeButtonGroup.addButton(dialog.priceModeNetworkRadio)
    dialog._priceModeRow = QWidget()
    priceModeLayout = QHBoxLayout(dialog._priceModeRow)
    priceModeLayout.setContentsMargins(0, 0, 0, 0)
    priceModeLayout.addWidget(dialog.priceModeSingleRadio)
    priceModeLayout.addWidget(dialog.priceModeNetworkRadio)
    priceModeLayout.addStretch()

    # The vector picker's LABEL stays in the parent form (so it aligns with the cost-raster rows) while
    # only the FIELD swaps with the mode via a stacked widget. The flow field itself lives in the Pipe
    # Diameter box (it replaces the constant M there in Network mode).
    dialog._priceVectorLabel = QLabel("Pipeline Vector:")
    dialog._priceVectorStack = QStackedWidget()
    dialog._priceVectorStack.addWidget(dialog.pipelineVectorDropdown)  # index 0 = Single
    dialog._priceVectorStack.addWidget(dialog.priceNetworkVectorDropdown)  # index 1 = Network

    selectionLayout.addRow(dialog._priceModeRow)
    selectionLayout.addRow(dialog._priceVectorLabel, dialog._priceVectorStack)
    selectionLayout.addRow(QLabel("Land Use Costs Raster (F<sub>lu</sub>):"), dialog.landUseCostsDropdown)
    selectionLayout.addRow(QLabel("Slope Costs Raster (F<sub>s</sub>):"), dialog.slopeCostsDropdown)
    selectionLayout.addRow(QLabel("Corridors Costs Raster (F<sub>c</sub>):"), dialog.corridorsCostsDropdown)
    selectionLayout.addRow(QLabel("Crossings Costs Raster (F<sub>ci</sub>):"), dialog.crossingsCostsDropdown)
    selectionLayout.addRow(QLabel("Infrastructure Vector (for N):"), dialog.crossingsVectorDropdown)
    left_layout.addWidget(make_group_box("Select Cost Rasters and Vector", selectionLayout))

    # Network mode is experimental — hide the mode row when off (Single only).
    if not dialog.network_mode_experimental:
        dialog._priceModeRow.setVisible(False)
        dialog._priceVectorStack.setCurrentIndex(0)

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

    # Flow input swaps with the mode: Single = the constant CO₂ mass flow M (kg/s); Network = the
    # per-segment flow field (Mt/yr). Only the FIELD is stacked; the LABEL stays in the parent form so it
    # aligns with the other Pipe Diameter rows (its text is swapped on the mode toggle).
    dialog._priceFlowLabel = QLabel("CO₂ Mass Flow Rate (M, kg/s):")
    dialog._priceFlowInputStack = QStackedWidget()
    dialog._priceFlowInputStack.addWidget(dialog.co2MassFlowRateInput)  # index 0 = Single (constant M)
    dialog._priceFlowInputStack.addWidget(dialog.priceNetworkFlowField)  # index 1 = Network (flow field)

    dLayout.addRow(QLabel("Friction Factor (λ):"), dialog.frictionFactorInput)
    dLayout.addRow(dialog._priceFlowLabel, dialog._priceFlowInputStack)
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

    # Network mode: the radio swaps BOTH stacks together — the vector picker (Pipeline ↔ Network) and
    # the flow input in the Pipe Diameter box (constant M ↔ per-segment flow field).
    def _on_price_mode_toggled():
        network = dialog.priceModeNetworkRadio.isChecked()
        idx = 1 if network else 0
        dialog._priceVectorStack.setCurrentIndex(idx)
        dialog._priceFlowInputStack.setCurrentIndex(idx)
        dialog._priceVectorLabel.setText("Network Vector:" if network else "Pipeline Vector:")
        dialog._priceFlowLabel.setText("Flow field (Mt/yr):" if network else "CO₂ Mass Flow Rate (M, kg/s):")
        update_pipeline_length(dialog)  # the length field follows the active (pipeline/network) vector

    dialog.priceModeNetworkRadio.toggled.connect(lambda checked: _on_price_mode_toggled())

    def _update_price_flow_field():
        dialog.priceNetworkFlowField.setLayer(layer_from_dropdown(dialog.priceNetworkVectorDropdown))

    dialog.priceNetworkVectorDropdown.currentIndexChanged.connect(_update_price_flow_field)
    dialog.priceNetworkVectorDropdown.currentIndexChanged.connect(lambda: update_pipeline_length(dialog))
    _update_price_flow_field()
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

    network_mode = dialog.network_mode_experimental and dialog.priceModeNetworkRadio.isChecked()
    log("Calculating network price..." if network_mode else "Calculating pipeline price...")

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

    # Capture the route geometry as plain coordinate pairs on the main thread. Network mode reads the
    # 2a network (each feature = a segment with its own flow + junction flag); Single = one pipeline.
    edges = None
    segments = None
    if network_mode:
        network_layer = layer_from_dropdown(dialog.priceNetworkVectorDropdown)
        if not network_layer:
            raise ValueError("Network vector must be selected.")
        flow_field = dialog.priceNetworkFlowField.currentField()
        if not flow_field:
            raise ValueError("Select the network 'flow' field (Mt/yr).")
        edges = _read_network_edges(network_layer, flow_field, log)
        if not edges:
            raise ValueError("The network vector has no usable segments with a flow value.")
    else:
        pipeline_layer = layer_from_dropdown(dialog.pipelineVectorDropdown)
        if not pipeline_layer:
            raise ValueError("Pipeline vector must be selected.")
        segments = _polyline_segments(pipeline_layer)

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
        "network": network_mode,
        "mode": mode,
        "cost_specs": cost_specs,
        "cost_paths": cost_paths,
        "segments": segments,
        "edges": edges,
        "infra_geoms": infra_geoms,
        "eng": eng,
        "log": log,
    }


def _polyline_segments(layer):
    """Flatten a line layer's features into ``(x1, y1, x2, y2)`` vertex-pair segments."""
    segments = []
    for feature in layer.getFeatures():
        segments.extend(_polyline_segments_from_geom(feature.geometry()))
    return segments


def _read_network_edges(layer, flow_field, log):
    """Read each network feature as an edge: ``{"flow", "junction", "segments"}``.

    ``junction`` comes from the 2a ``junction`` field (1 where flows merge); absent → no junction
    boosters (a warning is logged, since a non-2a network won't carry the flag).
    """
    has_junction = layer.fields().indexOf("junction") >= 0
    if not has_junction:
        log("  ⚠️ No 'junction' field — junction boosters skipped (use a Level-2a network.gpkg for them).")

    edges = []
    for feature in layer.getFeatures():
        flow = feature[flow_field]
        if flow is None:
            continue
        junction = bool(feature["junction"]) if has_junction else False
        segs = _polyline_segments_from_geom(feature.geometry())
        if segs:
            edges.append({"flow": float(flow), "junction": junction, "segments": segs})

    n_junctions = sum(1 for e in edges if e["junction"])
    log(f"  Network: {len(edges)} segment(s), {n_junctions} junction(s)")
    return edges


def _polyline_segments_from_geom(geom):
    """Vertex-pair segments of a single line geometry."""
    parts = geom.asMultiPolyline() if geom.isMultipart() else [geom.asPolyline()]
    return [
        (line[i].x(), line[i].y(), line[i + 1].x(), line[i + 1].y()) for line in parts for i in range(len(line) - 1)
    ]


def _price_work(params: dict) -> dict:
    """Background thread: sample cost factors along the route(s), then compute CAPEX."""
    log = params["log"]

    if params["network"]:
        edges = extract_network_values(
            params["edges"], params["cost_specs"], params["cost_paths"], params["infra_geoms"], params["mode"], log
        )
        return compute_network_capex(edges, params["eng"], log)

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

        # --- Intro (moved here from the tab header to free vertical space) ---
        intro_label = QLabel(
            "<p style='font-size:13px; color:#dddddd; line-height:1.5;'>"
            "ⓘ Estimates the total pipeline investment cost (<b>I<sub>total</sub></b>) from the selected "
            "pipeline (or network) vector and cost rasters.<br><br>"
            "<b>Single</b> sizes the whole pipeline with one <b>diameter (D)</b> from the full length. "
            "<b>Network</b> sizes <b>each segment</b> for its own flow — trunks (merged spurs) get a larger "
            "diameter, and a booster is added where flows merge (junction).<br><br>"
            "The <b>segment length</b> (booster spacing) is derived from the pressure budget "
            "(total ÷ admissible pressure drop; 150 km by default). "
            "<b>Precise</b> resamples the cost rasters and iterates over every GIS cell crossed "
            "(L<sub>cell</sub> = exact length inside each cell); <b>Fast</b> samples 5 points along each "
            "vector segment on the original rasters (max value, L<sub>seg</sub> = segment length)."
            "</p>"
        )
        intro_label.setWordWrap(True)
        grid_layout.addWidget(intro_label, 0, 0, 1, 2)

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
        grid_layout.addWidget(D_formula_label, 1, 0, Qt.AlignmentFlag.AlignCenter)
        grid_layout.addWidget(D_explanation, 1, 1)

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
        grid_layout.addWidget(Ip_formula_label, 2, 0, Qt.AlignmentFlag.AlignCenter)
        grid_layout.addWidget(Ip_explanation, 2, 1)

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
        grid_layout.addWidget(Sc_formula_label, 3, 0, Qt.AlignmentFlag.AlignCenter)
        grid_layout.addWidget(Sc_explanation, 3, 1)

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
        grid_layout.addWidget(Ib_formula_label, 4, 0, Qt.AlignmentFlag.AlignCenter)
        grid_layout.addWidget(Ib_explanation, 4, 1)

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
        grid_layout.addWidget(Itotal_formula_label, 5, 0, Qt.AlignmentFlag.AlignCenter)
        grid_layout.addWidget(Itotal_explanation, 5, 1)

        scroll_area = QScrollArea()
        scroll_area.setWidget(scroll_content)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll_area)
        self.setLayout(outer_layout)
