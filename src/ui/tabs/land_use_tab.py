import os
from functools import partial
from typing import TYPE_CHECKING

from qgis.core import QgsPalettedRasterRenderer, QgsProject, QgsRasterLayer
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ...constants.land_use import COMET_LAND_USE_COSTS
from ...core.factors.land_use import create_land_use_cost_raster
from ...task_manager import run_task
from ...utils import get_layer_path, layer_from_dropdown
from ...widgets.browse_row import add_output_path_row

if TYPE_CHECKING:
    from ...analysis_dialog import AnalysisDialog


def setup_land_use_tab(dialog: "AnalysisDialog", layout: QFormLayout):
    """Sets up the Land Use tab."""
    layout.addRow(QLabel("Select Land Use Layer:"), dialog.landUseComboBox)

    dialog.landUseCostTable = QTableWidget()
    dialog.landUseCostTable.setColumnCount(3)
    dialog.landUseCostTable.setHorizontalHeaderLabels(["Class ID", "Class Name", "Cost"])
    dialog.landUseCostTable.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    layout.addRow(dialog.landUseCostTable)

    tableButtonsLayout = QHBoxLayout()
    dialog.showCometValuesButton = QPushButton("Show COMET Values")
    dialog.landUsePopulateCometButton = QPushButton("Populate according to COMET")
    dialog.landUsePopulateCometButton.setObjectName("populateCometButton")
    tableButtonsLayout.addWidget(dialog.showCometValuesButton)
    tableButtonsLayout.addWidget(dialog.landUsePopulateCometButton)
    layout.addRow(tableButtonsLayout)

    outputFileLayout = add_output_path_row(
        dialog, "landUseCostsRasterPath", "landUseBrowse", "tif", "Choose output path for Land Use Costs Raster"
    )
    layout.addRow(outputFileLayout)

    dialog.create_land_use_costs_button = QPushButton("Create Land Use Costs Raster")
    layout.addRow(dialog.create_land_use_costs_button)


def connect_land_use_signals(dialog: "AnalysisDialog"):
    """Connects signals for the Land Use tab."""
    dialog.landUseComboBox.currentIndexChanged.connect(
        lambda: on_land_use_layer_changed(dialog), Qt.ConnectionType.QueuedConnection
    )
    dialog.create_land_use_costs_button.clicked.connect(
        lambda checked: run_task(
            dialog,
            "Create Land Use Cost Raster",
            work=_land_use_work,
            prepare=_land_use_prepare,
            publish=_land_use_publish,
        )
    )
    dialog.showCometValuesButton.clicked.connect(lambda: open_comet_values_dialog(dialog))

    populate_handler = partial(populate_land_use_table_with_comet_defaults, dialog)
    dialog.landUsePopulateCometButton.clicked.connect(populate_handler)

    dialog.log_message("Connection for 'Populate according to COMET' button has been established.", "Land Use")


def on_land_use_layer_changed(dialog: "AnalysisDialog"):
    """Handles changes in the land use layer selection, populating the table."""
    populate_land_use_table(dialog, dialog.landUseComboBox.currentData())


def _land_use_prepare(dialog: "AnalysisDialog") -> dict:
    """Main thread: read the cost table + selected layer + output path, resolve to a source path."""
    land_use_layer = layer_from_dropdown(dialog.landUseComboBox)
    class_costs = get_land_use_costs(dialog)

    if not land_use_layer:
        raise ValueError("No land use layer selected.")
    if not class_costs:
        raise ValueError("No class costs defined in the table. Please add costs.")

    output_path = dialog.landUseCostsRasterPath.text()
    if not output_path:
        raise ValueError("No output path specified for Land Use Costs Raster.")

    dialog.log_message("Creating Land Use Costs Raster...", "Land Use")
    return {
        "source_path": get_layer_path(land_use_layer),
        "class_costs": class_costs,
        "output_path": output_path,
        "log": lambda msg: dialog.log_message(msg, "Land Use"),
    }


def _land_use_work(params: dict) -> str:
    """Background thread: build the cost raster, return its path."""
    return create_land_use_cost_raster(
        params["source_path"], params["class_costs"], params["output_path"], log=params["log"]
    )


def _land_use_publish(dialog: "AnalysisDialog", output_path: str):
    """Main thread: load the created cost raster into the project."""
    layer_name = os.path.splitext(os.path.basename(output_path))[0]
    new_layer = QgsRasterLayer(output_path, layer_name)
    if not new_layer.isValid():
        raise RuntimeError("Failed to load the created Land Use Costs raster.")
    QgsProject.instance().addMapLayer(new_layer)
    dialog.log_message(f"Land Use Costs Raster created successfully at: {output_path}", "Land Use")


def get_land_use_costs(dialog: "AnalysisDialog"):
    """Extracts land use class costs from the table."""
    costs = {}
    for row in range(dialog.landUseCostTable.rowCount()):
        try:
            class_id = float(dialog.landUseCostTable.item(row, 0).text())
            cost = float(dialog.landUseCostTable.item(row, 2).text())
            costs[class_id] = cost
        except (ValueError, AttributeError):
            continue
    return costs


def populate_land_use_table(dialog: "AnalysisDialog", layer_id: str):
    """Populates the table with unique land use classes from the selected raster's symbology."""
    dialog.landUseCostTable.setRowCount(0)

    if not layer_id:
        return

    terrain_layer = QgsProject.instance().mapLayer(layer_id)
    if not isinstance(terrain_layer, QgsRasterLayer):
        dialog.log_message("Selected layer is not a valid raster layer.", "Land Use")
        return

    renderer = terrain_layer.renderer()
    if not isinstance(renderer, QgsPalettedRasterRenderer):
        dialog.log_message("Selected layer does not use a Paletted/Unique Values renderer.", "Land Use")
        return

    classes = renderer.classes()
    if not classes:
        dialog.log_message("No class data available in the renderer.", "Land Use")
        return

    for entry in classes:
        row_position = dialog.landUseCostTable.rowCount()
        dialog.landUseCostTable.insertRow(row_position)

        class_id_item = QTableWidgetItem(str(entry.value))
        class_id_item.setFlags(class_id_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
        dialog.landUseCostTable.setItem(row_position, 0, class_id_item)

        class_name_item = QTableWidgetItem(entry.label)
        class_name_item.setFlags(class_name_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
        dialog.landUseCostTable.setItem(row_position, 1, class_name_item)

        cost_item = QTableWidgetItem("1.0")
        cost_item.setFlags(cost_item.flags() | Qt.ItemFlag.ItemIsEditable)
        dialog.landUseCostTable.setItem(row_position, 2, cost_item)

    dialog.log_message(f"{len(classes)} land use classes loaded from layer style.", "Land Use")


def get_unique_values_from_raster_renderer(renderer: QgsPalettedRasterRenderer):
    """Extracts unique values from a paletted raster renderer."""
    return [c.value for c in renderer.classes()]


def populate_land_use_table_with_comet_defaults(dialog: "AnalysisDialog"):
    """
    Populates the land use cost table with values from the COMET project.
    This function performs a strict check to ensure the selected layer is
    compatible with COMET/COSC standards before populating.
    """
    try:
        layer_id = dialog.landUseComboBox.currentData()
        if not layer_id:
            dialog.log_message("Cannot populate: No land use layer selected.", "Land Use")
            return

        layer = QgsProject.instance().mapLayer(layer_id)
        if not isinstance(layer, QgsRasterLayer):
            dialog.log_message("Cannot populate: The selected layer is not a valid raster layer.", "Land Use")
            return

        renderer = layer.renderer()
        if not isinstance(renderer, QgsPalettedRasterRenderer):
            dialog.log_message(
                "Cannot populate: The selected raster does not have a paletted (unique values) renderer.", "Land Use"
            )
            return

        unique_values = get_unique_values_from_raster_renderer(renderer)
        comet_class_ids = set(COMET_LAND_USE_COSTS)

        unique_values_as_int = {int(v) for v in unique_values}

        if not unique_values_as_int.intersection(comet_class_ids):
            dialog.log_message(
                "Cannot populate: The selected land use layer must be a 'Carta de Ocupação do Solo Conjuntural' from Direção-Geral do Território.",
                "Land Use",
            )
            return

        populated_count = 0
        for row in range(dialog.landUseCostTable.rowCount()):
            class_id_item = dialog.landUseCostTable.item(row, 0)
            cost_item = dialog.landUseCostTable.item(row, 2)

            if class_id_item and cost_item:
                try:
                    class_id = int(float(class_id_item.text()))
                    if class_id in COMET_LAND_USE_COSTS:
                        cost_item.setText(str(COMET_LAND_USE_COSTS[class_id]))
                        populated_count += 1
                except ValueError:
                    continue

        if populated_count > 0:
            dialog.log_message(
                f"Land use costs populated with COMET default values for {populated_count} classes.", "Land Use"
            )
        else:
            dialog.log_message(
                "A COMET-compatible layer was detected, but no matching class IDs were found in the table to update.",
                "Land Use",
            )

    except Exception as e:
        dialog.log_message(f"An unexpected error occurred while populating COMET values: {e}", "Land Use")


def open_comet_values_dialog(parent_dialog):
    """Opens the dialog that displays the COMET values table."""
    dialog = CometValuesDialog(parent_dialog)
    dialog.exec()


class CometValuesDialog(QDialog):
    """A dialog to display the COMET land use class costs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("COMET Project - Land Use Cost Factors")
        self.setMinimumSize(800, 510)
        self.setStyleSheet("""
            QTableWidget { font-size: 12px; }
            QHeaderView::section { padding: 4px; font-weight: bold; }
        """)

        layout = QVBoxLayout()
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Class ID", "COSc Thematic Class", "COMET Land Use", "Cost Factor"])
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        data = [
            ("100", "Artificializado", "Áreas urbanas e associadas", "1.8"),
            ("211", "Culturas anuais de outono/inverno", "Terras cultivadas", "1.1"),
            ("212", "Culturas anuais de primavera/verão", "", ""),
            ("213", "Outras áreas agrícolas", "", ""),
            ("311", "Sobreiro e Azinheira", "Florestas", "1.3"),
            ("312", "Eucalipto", "", ""),
            ("313", "Outras folhosas", "", ""),
            ("321", "Pinheiro bravo", "", ""),
            ("322", "Pinheiro manso", "", ""),
            ("323", "Outras resinosas", "", ""),
            ("410", "Matos", "Áreas áridas", "1.1"),
            ("420", "Vegetação herbácea espontânea", "", ""),
            ("500", "Superfícies sem vegetação", "Áreas não povoadas", "1.0"),
            ("610", "Zonas húmidas", "Zonas regularmente inundadas", "1.2"),
            ("620", "Água", "Corpos de água", "4.0"),
            ("-", "-", "Áreas protegidas", "10"),
        ]

        table.setRowCount(len(data))
        for row, row_data in enumerate(data):
            for col, cell_data in enumerate(row_data):
                table.setItem(row, col, QTableWidgetItem(cell_data))

        table.setSpan(1, 2, 3, 1)
        table.setSpan(1, 3, 3, 1)
        table.setSpan(4, 2, 6, 1)
        table.setSpan(4, 3, 6, 1)
        table.setSpan(10, 2, 2, 1)
        table.setSpan(10, 3, 2, 1)

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(table)
        self.setLayout(layout)
