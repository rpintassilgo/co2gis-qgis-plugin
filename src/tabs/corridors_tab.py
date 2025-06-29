from typing import TYPE_CHECKING
from PyQt5.QtWidgets import (
    QLabel, QComboBox, QLineEdit, QPushButton, QHBoxLayout, QFormLayout, QTableWidget, QHeaderView, QCheckBox
)
from PyQt5.QtCore import Qt
from qgis.core import QgsProject, QgsRasterLayer
from ..task_manager import run_in_background
from ..utils import select_output_file

if TYPE_CHECKING:
    from ..analysis_dialog import AnalysisDialog

def setup_corridors_tab(dialog: 'AnalysisDialog', layout: QFormLayout):
    dialog.corridorComboBox = QComboBox()
    layout.addRow(QLabel("Select Corridor Vector:"), dialog.corridorComboBox)
    dialog.corridorRefRasterComboBox = QComboBox()
    layout.addRow(QLabel("Select Reference Raster:"), dialog.corridorRefRasterComboBox)

    dialog.corridorPresentOffshoreInput = QLineEdit()
    dialog.corridorPresentOffshoreInput.setPlaceholderText("Cost for corridor present offshore")
    dialog.corridorPresentOffshoreInput.setText("2.7")
    layout.addRow(QLabel("Cost for corridor present offshore:"), dialog.corridorPresentOffshoreInput)

    dialog.corridorPresentOnshoreInput = QLineEdit()
    dialog.corridorPresentOnshoreInput.setPlaceholderText("Cost for corridor present onshore")
    dialog.corridorPresentOnshoreInput.setText("0.9")
    layout.addRow(QLabel("Cost for corridor present onshore:"), dialog.corridorPresentOnshoreInput)

    dialog.corridorAbsentOffshoreInput = QLineEdit()
    dialog.corridorAbsentOffshoreInput.setPlaceholderText("Cost for corridor absent offshore")
    dialog.corridorAbsentOffshoreInput.setText("3")
    layout.addRow(QLabel("Cost for corridor absent offshore:"), dialog.corridorAbsentOffshoreInput)

    dialog.corridorAbsentOnshoreInput = QLineEdit()
    dialog.corridorAbsentOnshoreInput.setPlaceholderText("Cost for corridor absent onshore")
    dialog.corridorAbsentOnshoreInput.setText("1")
    layout.addRow(QLabel("Cost for corridor absent onshore:"), dialog.corridorAbsentOnshoreInput)

    dialog.corridorLandUseComboBox = QComboBox()
    layout.addRow(QLabel("Select Land Use Layer:"), dialog.corridorLandUseComboBox)

    dialog.corridorLandUseTable = QTableWidget()
    dialog.corridorLandUseTable.setColumnCount(3)
    dialog.corridorLandUseTable.setHorizontalHeaderLabels(["Class ID", "Class Name", "Water Body"])
    dialog.corridorLandUseTable.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    layout.addRow(dialog.corridorLandUseTable)

    dialog.corridorOutputPath = QLineEdit()
    dialog.corridorOutputPath.setPlaceholderText("Choose output path for Raster")
    dialog.corridorBrowse = QPushButton("Browse")
    dialog.corridorBrowse.clicked.connect(lambda: select_output_file(dialog.corridorOutputPath, "tif"))
    outputCorridorLayout = QHBoxLayout()
    outputCorridorLayout.addWidget(dialog.corridorOutputPath)
    outputCorridorLayout.addWidget(dialog.corridorBrowse)
    layout.addRow(outputCorridorLayout)
    dialog.runCreateRasterFromCorridorButton = QPushButton("Create Corridors Costs Raster")
    layout.addRow(dialog.runCreateRasterFromCorridorButton)

    # Populate corridorLandUseComboBox with raster layers
    for layer in QgsProject.instance().mapLayers().values():
        if isinstance(layer, QgsRasterLayer):
            dialog.corridorLandUseComboBox.addItem(layer.name(), layer.id())

    # Connect dropdown change to table population
    dialog.corridorLandUseComboBox.currentIndexChanged.connect(
        lambda: populate_corridor_land_use_table(dialog, dialog.corridorLandUseComboBox.currentData())
    )

    # Initial population if any layer is selected
    if dialog.corridorLandUseComboBox.count() > 0:
        populate_corridor_land_use_table(dialog, dialog.corridorLandUseComboBox.currentData())

def populate_corridor_land_use_table(dialog, layer_id):
    from qgis.core import QgsProject, QgsRasterLayer, QgsPalettedRasterRenderer
    from PyQt5.QtWidgets import QTableWidgetItem, QCheckBox
    from PyQt5.QtCore import Qt
    dialog.corridorLandUseTable.setRowCount(0)
    if not layer_id:
        return
    layer = QgsProject.instance().mapLayer(layer_id)
    if not isinstance(layer, QgsRasterLayer):
        return
    renderer = layer.renderer()
    if not hasattr(renderer, 'classes'):
        return
    classes = renderer.classes()
    for entry in classes:
        row_position = dialog.corridorLandUseTable.rowCount()
        dialog.corridorLandUseTable.insertRow(row_position)
        class_id_item = QTableWidgetItem(str(entry.value))
        class_id_item.setFlags(class_id_item.flags() ^ Qt.ItemIsEditable)
        dialog.corridorLandUseTable.setItem(row_position, 0, class_id_item)
        class_name_item = QTableWidgetItem(entry.label)
        class_name_item.setFlags(class_name_item.flags() ^ Qt.ItemIsEditable)
        dialog.corridorLandUseTable.setItem(row_position, 1, class_name_item)
        water_checkbox = QCheckBox()
        water_checkbox.setChecked(False)
        water_checkbox.setStyleSheet("margin-left:50%; margin-right:50%;")
        dialog.corridorLandUseTable.setCellWidget(row_position, 2, water_checkbox) 