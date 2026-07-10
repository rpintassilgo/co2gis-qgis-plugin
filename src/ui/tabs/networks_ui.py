"""LCP-tab Network mode UI (experimental, gated by the Settings toggle).

Builds the Network *page* of the LCP tab's routing stack and wires its run button
to the star-routing core (:func:`src.core.networks.routing.route_star`). The page
is only reachable when ``dialog.network_mode_experimental`` is on (the mode radio +
stack live in ``lcp_tab``), but the widgets are always created so the dropdown
registry resolves. The combined-raster picker is shared with Single mode
(``dialog.lcpInputDropdown``), so it is not built here.

Follows the 3-phase task contract: ``prepare`` (main thread) reads widgets and
resolves layers, then delegates layer→model conversion to ``core.networks.io``;
``work`` (background) runs ``route_star``; ``publish`` (main thread) loads the
merged network layer.
"""

import os
from typing import TYPE_CHECKING

from qgis.core import QgsProject, QgsVectorLayer
from qgis.gui import QgsFieldComboBox
from qgis.PyQt.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QWidget,
)

from ...core.networks.io import build_nodes
from ...core.networks.milp import missing_solver_packages
from ...core.networks.model import SINK, SOURCE
from ...core.networks.trunks import route_network_heuristic, route_network_milp
from ...task_manager import run_task
from ...utils import get_layer_path, layer_from_dropdown
from ...widgets.browse_row import add_output_path_row
from ..engineering_inputs import read_engineering_inputs

if TYPE_CHECKING:
    from ...analysis_dialog import AnalysisDialog

# Candidate-graph density presets → (grid divisions per bbox side, k nearest-neighbour arcs). Finer →
# more junction nodes (one r.cost each) and a bigger MILP, closer to the true optimum. The spacing is
# derived from the sources/sinks extent at run time, so these are CRS-unit-free.
CANDIDATE_DENSITY = {
    "Coarse (fast)": (5, 6),
    "Medium": (8, 6),
    "Fine (slow)": (12, 8),
}
DEFAULT_CANDIDATE_DENSITY = "Medium"


def setup_network_page(dialog: "AnalysisDialog") -> QWidget:
    """Build the Network page (sources/sinks, field mapping, output, run button).

    Returns a ``QWidget`` for the caller to place in the routing stack. The
    combined-raster picker is shared with Single mode and lives on the tab, not
    here. Units are Mt/yr (base unit Mt); at Level 1 flow/capacity/target are only
    read to seed the network — the physics uses them at Level 3.
    """
    page = QWidget()
    layout = QFormLayout(page)

    # Optimization method: Heuristic vs MILP (Level 3). Two ways to design the network — like Price
    # Estimation's precise/fast — not a fallback. MILP needs the optional solver (PuLP + HiGHS); when it
    # isn't installed the radio is disabled with a tooltip naming what to install.
    dialog.networkMethodHeuristicRadio = QRadioButton("Heuristic (fast)")
    dialog.networkMethodMilpRadio = QRadioButton("MILP (optimal)")
    dialog.networkMethodHeuristicRadio.setChecked(True)
    missing = missing_solver_packages()
    dialog.networkMethodMilpRadio.setEnabled(not missing)
    if missing:
        dialog.networkMethodMilpRadio.setToolTip(
            "Optimal MILP network design is disabled: the solver isn't installed.\n"
            f"Install the missing package(s) in the QGIS Python environment: pip install {' '.join(missing)}"
        )
    else:
        dialog.networkMethodMilpRadio.setToolTip(
            "Provably minimum-cost network design: picks which links to build, the pipe sizes, and the "
            "trunks that form where flows merge, to meet the capture target at least cost."
        )
    dialog.networkMethodButtonGroup = QButtonGroup()
    dialog.networkMethodButtonGroup.addButton(dialog.networkMethodHeuristicRadio)
    dialog.networkMethodButtonGroup.addButton(dialog.networkMethodMilpRadio)
    methodRow = QWidget()
    methodLayout = QHBoxLayout(methodRow)
    methodLayout.setContentsMargins(0, 0, 0, 0)
    methodLayout.addWidget(dialog.networkMethodHeuristicRadio)
    methodLayout.addWidget(dialog.networkMethodMilpRadio)
    methodLayout.addStretch()
    layout.addRow(QLabel("Optimization method:"), methodRow)

    dialog.networkSourcesDropdown = QComboBox()
    dialog.networkFlowField = QgsFieldComboBox()
    layout.addRow(QLabel("Sources layer (points):"), dialog.networkSourcesDropdown)
    layout.addRow(QLabel("Flow field (Mt/yr):"), dialog.networkFlowField)

    dialog.networkSinksDropdown = QComboBox()
    dialog.networkCapacityField = QgsFieldComboBox()
    layout.addRow(QLabel("Sinks layer (points):"), dialog.networkSinksDropdown)
    layout.addRow(QLabel("Injection rate field (Mt/yr):"), dialog.networkCapacityField)

    # Capture target is a MILP-only input (the optimizer picks which sources to connect to meet it).
    # The heuristic connects every source, so the row is shown only when MILP is selected.
    dialog.networkCaptureTargetInput = QLineEdit()
    dialog.networkCaptureTargetInput.setPlaceholderText("Mt/yr — minimum total CO₂ to capture")
    dialog.networkCaptureTargetInput.setToolTip(
        "Minimum total CO₂ the network must capture; the MILP picks which sources to connect to meet it "
        "at least cost. Used by MILP optimization only."
    )
    # Candidate-graph density: how fine a junction grid the MILP searches over (one r.cost per node, so
    # finer → closer to the true optimum but slower). Derives the grid spacing from the sources/sinks
    # extent, so the user needs no CRS-unit knowledge. Inline (not in Settings) to iterate quickly.
    dialog.networkDensityDropdown = QComboBox()
    for label in CANDIDATE_DENSITY:
        dialog.networkDensityDropdown.addItem(label)
    dialog.networkDensityDropdown.setCurrentText(DEFAULT_CANDIDATE_DENSITY)
    dialog.networkDensityDropdown.setToolTip(
        "How fine a junction grid the MILP searches: Coarse is fastest, Fine is closest to the true "
        "optimum but runs more r.cost passes. Start Coarse and refine."
    )

    dialog._networkMilpRow = QWidget()
    milpForm = QFormLayout(dialog._networkMilpRow)
    milpForm.setContentsMargins(0, 0, 0, 0)
    milpForm.addRow(QLabel("Capture target (Mt/yr):"), dialog.networkCaptureTargetInput)
    milpForm.addRow(QLabel("Candidate-graph density:"), dialog.networkDensityDropdown)
    layout.addRow(dialog._networkMilpRow)
    dialog._networkMilpRow.setVisible(False)  # Heuristic is the default → hidden until MILP is chosen

    outputRow = add_output_path_row(
        dialog, "networkOutputPath", "networkOutputBrowse", "gpkg", "Choose output path for the network vector"
    )
    layout.addRow(outputRow)

    dialog.network_button = QPushButton("Create Network (experimental)")
    layout.addRow(dialog.network_button)
    return page


def connect_network_signals(dialog: "AnalysisDialog"):
    """Wire the Network page: field combos follow their layers, and the run button."""

    def _update_flow_field():
        dialog.networkFlowField.setLayer(layer_from_dropdown(dialog.networkSourcesDropdown))

    def _update_capacity_field():
        dialog.networkCapacityField.setLayer(layer_from_dropdown(dialog.networkSinksDropdown))

    dialog.networkSourcesDropdown.currentIndexChanged.connect(_update_flow_field)
    dialog.networkSinksDropdown.currentIndexChanged.connect(_update_capacity_field)
    _update_flow_field()
    _update_capacity_field()

    # Capture target + density are MILP-only inputs → reveal them only when MILP is selected.
    dialog.networkMethodMilpRadio.toggled.connect(
        lambda checked: dialog._networkMilpRow.setVisible(dialog.networkMethodMilpRadio.isChecked())
    )

    dialog.network_button.clicked.connect(
        lambda checked: run_task(
            dialog, "Create Network", work=_network_work, prepare=_network_prepare, publish=_network_publish
        )
    )


def _bbox_spacing(nodes, divisions: int) -> float:
    """Junction-grid spacing (map units) = the sources/sinks extent divided into ``divisions`` per side.

    Derives the candidate-graph resolution from the data's own footprint, so the density presets are
    CRS-unit-free. Raises if the anchors are coincident (a degenerate 0-extent grid).
    """
    xs = [n.x for n in nodes]
    ys = [n.y for n in nodes]
    extent = max(max(xs) - min(xs), max(ys) - min(ys))
    if extent <= 0:
        raise ValueError("Sources and sinks are coincident — cannot build a candidate grid.")
    return extent / divisions


def _network_prepare(dialog: "AnalysisDialog") -> dict:
    """Main thread: resolve layers/fields, build source/sink nodes, validate.

    Branches on the selected method: the heuristic needs only the layers; MILP additionally reads the
    capture target, the density preset (→ grid spacing + k), and the engineering inputs shared with CAPEX.
    """
    combined_layer = layer_from_dropdown(dialog.lcpInputDropdown)
    sources_layer = layer_from_dropdown(dialog.networkSourcesDropdown)
    sinks_layer = layer_from_dropdown(dialog.networkSinksDropdown)
    flow_field = dialog.networkFlowField.currentField()
    capacity_field = dialog.networkCapacityField.currentField()
    output_path = dialog.networkOutputPath.text().strip()

    if not all([combined_layer, sources_layer, sinks_layer, output_path]):
        raise ValueError("Combined raster, sources layer, sinks layer, and an output path must all be selected.")
    if not flow_field:
        raise ValueError("Select the sources 'flow' field.")
    if not capacity_field:
        raise ValueError("Select the sinks 'injection rate' field.")

    log = lambda msg: dialog.log_message(msg, "Network")  # noqa: E731
    raster_crs = combined_layer.crs()
    sources = build_nodes(sources_layer, SOURCE, flow_field, "flow", raster_crs, "S", log)
    sinks = build_nodes(sinks_layer, SINK, capacity_field, "capacity", raster_crs, "K", log)
    if not sources:
        raise ValueError("The sources layer has no usable point features.")
    if not sinks:
        raise ValueError("The sinks layer has no usable point features.")

    params = {
        "method": "milp" if dialog.networkMethodMilpRadio.isChecked() else "heuristic",
        "combined_path": get_layer_path(combined_layer),
        "sources": sources,
        "sinks": sinks,
        "output_path": output_path,
        "memory": dialog.rcost_memory_mb,
        "log": log,
    }

    if params["method"] == "milp":
        target_text = dialog.networkCaptureTargetInput.text().strip()
        if not target_text:
            raise ValueError("Enter a capture target (Mt/yr) — the minimum total CO₂ the network must move.")
        target = float(target_text)
        if target <= 0:
            raise ValueError("Capture target must be greater than zero.")
        divisions, k = CANDIDATE_DENSITY[dialog.networkDensityDropdown.currentText()]
        params.update(
            {
                "target": target,
                "spacing": _bbox_spacing(list(sources) + list(sinks), divisions),
                "k": k,
                "eng": read_engineering_inputs(dialog),
            }
        )
        log(f"MILP network design (target {target:g} Mt/yr, {dialog.networkDensityDropdown.currentText()})...")
    else:
        log(f"Routing {len(sources)} source(s) → nearest of {len(sinks)} sink(s)...")

    return params


def _network_work(params: dict) -> dict:
    """Background thread: run the selected network design (MILP or the nearest-sink heuristic)."""
    if params["method"] == "milp":
        return route_network_milp(
            params["combined_path"],
            params["sources"],
            params["sinks"],
            params["target"],
            params["output_path"],
            params["spacing"],
            params["eng"],
            k=params["k"],
            memory=params["memory"],
            log=params["log"],
        )
    return route_network_heuristic(
        params["combined_path"],
        params["sources"],
        params["sinks"],
        params["output_path"],
        memory=params["memory"],
        log=params["log"],
    )


def _network_publish(dialog: "AnalysisDialog", result: dict):
    """Main thread: load the network vector (per-segment ``flow`` — the trunks)."""
    network_path = result["network_path"]
    layer = QgsVectorLayer(network_path, os.path.splitext(os.path.basename(network_path))[0], "ogr")
    if not layer.isValid():
        raise RuntimeError(f"Failed to load network vector: {network_path}")
    QgsProject.instance().addMapLayer(layer)
    dialog.log_message(f"Network: {network_path}", "Network")

    # Each segment carries the flow it transports — trunks (merged spurs) carry the sum. Identify a
    # segment or style by 'flow' (graduated width) to see spurs thicken into trunks at the junctions.
    segments = result.get("segments", [])
    dialog.log_message(f"  {len(segments)} segment(s); flows (Mt/yr): {_summarize_flows(segments)}", "Network")
    if "selected" in result:  # MILP: log each built link with its chosen pipe size
        for arc in result["selected"]:
            dialog.log_message(
                f"  link {arc.u_id} → {arc.v_id}: flow {arc.flow:g} Mt/yr, D {arc.diameter * 1000:.0f} mm", "Network"
            )
    else:  # heuristic (greedy tree): the sources gathered into the network
        routes = result.get("routes", [])
        dialog.log_message(f"  {len(routes)} source(s) gathered into the tree", "Network")


def _summarize_flows(segments) -> str:
    """Short, sorted preview of the distinct segment flows (largest first)."""
    flows = sorted({round(float(seg.flow), 3) for seg in segments}, reverse=True)
    preview = ", ".join(f"{f:g}" for f in flows[:8])
    return preview + (" …" if len(flows) > 8 else "")
