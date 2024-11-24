from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer, QgsPalettedRasterRenderer
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QComboBox, QTableWidget, 
    QTableWidgetItem, QLineEdit, QPushButton, QHBoxLayout, 
    QFormLayout, QHeaderView, QTextEdit, QTabWidget, QMessageBox
)
from PyQt5.QtCore import Qt
from ..analysis import run_analysis
from .ui import setup_ui
from .dropdowns import populate_layer_dropdowns
from .dropdowns import refresh_layer_dropdown
from .land_use import populate_land_use_classes_table

class Dialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # TODO: eventually add a option to say the resolution of the raster in meters
        
        # explicitly declare attributes for typing
        self.terrainComboBox: QComboBox
        self.demComboBox: QComboBox
        self.pointsComboBox: QComboBox
        self.classTable: QTableWidget
        self.classify_button: QPushButton
        self.run_button: QPushButton
        self.clear_log_button: QPushButton
        self.demWeightInput: QLineEdit
        self.occupancyWeightInput: QLineEdit
        self.log_output: QTextEdit
        self.tabs: QTabWidget
        
        setup_ui(self)
        populate_layer_dropdowns(self)

        # connect signals
        self.classify_button.clicked.connect(lambda: populate_land_use_classes_table(self))
        self.run_button.clicked.connect(lambda: run_analysis(self))
        self.clear_log_button.clicked.connect(self.clear_logs)
        
        self.terrainComboBox.currentIndexChanged.connect(lambda: refresh_layer_dropdown(self.terrainComboBox, QgsRasterLayer))
        self.demComboBox.currentIndexChanged.connect(lambda: refresh_layer_dropdown(self.demComboBox, QgsRasterLayer))
        self.pointsComboBox.currentIndexChanged.connect(lambda: refresh_layer_dropdown(self.pointsComboBox, QgsVectorLayer))

    def get_weights(self):
        """Retrieve DEM and occupancy weights."""
        dem_weight = float(self.demWeightInput.text())
        occupancy_weight = float(self.occupancyWeightInput.text())
        return dem_weight, occupancy_weight

    def get_layers(self):
        """Retrieve selected layers from dropdowns."""
        terrain_layer_id = self.terrainComboBox.currentData()
        dem_layer_id = self.demComboBox.currentData()
        points_layer_id = self.pointsComboBox.currentData()
        terrain_layer = QgsProject.instance().mapLayer(terrain_layer_id)
        dem_layer = QgsProject.instance().mapLayer(dem_layer_id)
        points_layer = QgsProject.instance().mapLayer(points_layer_id)
        return terrain_layer, dem_layer, points_layer
     
    def all_fields_valid(self):
        """Check if all required fields are valid."""
        # Check if all dropdowns have a valid selection (not the placeholder)
        if (
            self.terrainComboBox.currentData() is None
            or self.demComboBox.currentData() is None
            or self.pointsComboBox.currentData() is None
        ):
            return False

        # Check if both weight inputs are filled
        if not self.demWeightInput.text().strip() or not self.occupancyWeightInput.text().strip():
            return False

        # Check if the Class Costs table has rows and at least one cost is greater than 0
        row_count = self.classTable.rowCount()
        if row_count == 0:
            return False

        # Ensure at least one cost value is greater than 0
        for row in range(row_count):
            cost_item = self.classTable.item(row, 2)
            if cost_item and float(cost_item.text()) > 0:
                return True  # Valid if at least one cost is greater than 0

        return False


    def log_message(self, message):
        self.log_output.append(message)
        
    def clear_logs(self):
        self.log_output.clear()