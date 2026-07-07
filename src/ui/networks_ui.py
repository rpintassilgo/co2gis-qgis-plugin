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
from qgis.PyQt.QtWidgets import QComboBox, QFormLayout, QLabel, QLineEdit, QPushButton, QWidget

from ..core.networks.io import build_nodes
from ..core.networks.model import SINK, SOURCE
from ..core.networks.routing import route_star
from ..task_manager import run_task
from ..utils import get_layer_path, layer_from_dropdown
from ..widgets.browse_row import add_output_folder_row

if TYPE_CHECKING:
    from ..analysis_dialog import AnalysisDialog


def setup_network_page(dialog: "AnalysisDialog") -> QWidget:
    """Build the Network page (sources/sinks, field mapping, output, run button).

    Returns a ``QWidget`` for the caller to place in the routing stack. The
    combined-raster picker is shared with Single mode and lives on the tab, not
    here. Units are Mt/yr (base unit Mt); at Level 1 flow/capacity/target are only
    read to seed the network — the physics uses them at Level 3.
    """
    page = QWidget()
    layout = QFormLayout(page)

    dialog.networkSourcesDropdown = QComboBox()
    dialog.networkFlowField = QgsFieldComboBox()
    layout.addRow(QLabel("Sources layer (points):"), dialog.networkSourcesDropdown)
    layout.addRow(QLabel("Flow field (Mt/yr):"), dialog.networkFlowField)

    dialog.networkSinksDropdown = QComboBox()
    dialog.networkCapacityField = QgsFieldComboBox()
    layout.addRow(QLabel("Sinks layer (points):"), dialog.networkSinksDropdown)
    layout.addRow(QLabel("Injection rate field (Mt/yr):"), dialog.networkCapacityField)

    dialog.networkCaptureTargetInput = QLineEdit()
    dialog.networkCaptureTargetInput.setPlaceholderText("Mt/yr (not used at Level 1)")
    dialog.networkCaptureTargetInput.setToolTip(
        "Reserved for the future MILP optimization; ignored by the Level-1 independent-star routing."
    )
    layout.addRow(QLabel("Capture target (Mt/yr):"), dialog.networkCaptureTargetInput)

    folderRow = add_output_folder_row(
        dialog, "networkOutputFolder", "networkOutputBrowse", "Choose output folder for the network"
    )
    layout.addRow(folderRow)

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

    dialog.network_button.clicked.connect(
        lambda checked: run_task(
            dialog, "Create Network", work=_network_work, prepare=_network_prepare, publish=_network_publish
        )
    )


def _network_prepare(dialog: "AnalysisDialog") -> dict:
    """Main thread: resolve layers/fields, build source/sink nodes, validate."""
    combined_layer = layer_from_dropdown(dialog.lcpInputDropdown)
    sources_layer = layer_from_dropdown(dialog.networkSourcesDropdown)
    sinks_layer = layer_from_dropdown(dialog.networkSinksDropdown)
    flow_field = dialog.networkFlowField.currentField()
    capacity_field = dialog.networkCapacityField.currentField()
    output_dir = dialog.networkOutputFolder.text().strip()

    if not all([combined_layer, sources_layer, sinks_layer, output_dir]):
        raise ValueError("Combined raster, sources layer, sinks layer, and an output folder must all be selected.")
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

    log(f"Routing {len(sources)} source(s) → nearest of {len(sinks)} sink(s)...")
    return {
        "combined_path": get_layer_path(combined_layer),
        "sources": sources,
        "sinks": sinks,
        "output_dir": output_dir,
        "memory": dialog.rcost_memory_mb,
        "log": log,
    }


def _network_work(params: dict) -> dict:
    """Background thread: run the star routing."""
    return route_star(
        params["combined_path"],
        params["sources"],
        params["sinks"],
        params["output_dir"],
        memory=params["memory"],
        log=params["log"],
    )


def _network_publish(dialog: "AnalysisDialog", result: dict):
    """Main thread: load the merged network layer and log a per-edge summary."""
    network_path = result["network_path"]
    layer_name = os.path.splitext(os.path.basename(network_path))[0]
    layer = QgsVectorLayer(network_path, layer_name, "ogr")
    if not layer.isValid():
        raise RuntimeError(f"Failed to load network vector: {network_path}")
    QgsProject.instance().addMapLayer(layer)
    dialog.log_message(f"Network created at: {network_path}", "Network")
    for edge in result["edges"]:
        dialog.log_message(
            f"  {edge.source_id} → {edge.sink_id}: length={edge.length:.1f} m, cost={edge.cost:.2f}", "Network"
        )
