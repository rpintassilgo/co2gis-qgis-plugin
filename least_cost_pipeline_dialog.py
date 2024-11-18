from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer, QgsPalettedRasterRenderer
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QComboBox, QTableWidget, 
    QTableWidgetItem, QLineEdit, QPushButton, QHBoxLayout, 
    QFormLayout, QHeaderView, QTextEdit, QTabWidget, QMessageBox
)
from PyQt5.QtCore import Qt
from .least_cost_pipeline_utils import run_r_cost, run_r_drain
from .ui import setup_ui

class LeastCostPipelineDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        setup_ui(self)  # Call the function to set up the UI

        # Connect signals and populate dropdowns
        self.classify_button.clicked.connect(self.classify_terrain_layer)
        self.run_button.clicked.connect(self.run_analysis)
        self.clear_log_button.clicked.connect(self.clear_logs)
        self.populate_layer_dropdowns()
        
        self.terrainComboBox.currentIndexChanged.connect(lambda: self.refresh_layer_dropdown(self.terrainComboBox, QgsRasterLayer))
        self.demComboBox.currentIndexChanged.connect(lambda: self.refresh_layer_dropdown(self.demComboBox, QgsRasterLayer))
        self.pointsComboBox.currentIndexChanged.connect(lambda: self.refresh_layer_dropdown(self.pointsComboBox, QgsVectorLayer))

    def classify_terrain_layer(self):
        """Classify the raster layer using a Paletted/Unique Values renderer."""
        # Get the selected terrain layer
        layer_id = self.terrainComboBox.currentData()
        terrain_layer = QgsProject.instance().mapLayer(layer_id)
        if not isinstance(terrain_layer, QgsRasterLayer):
            self.log_message("Selected layer is not a valid raster layer.")
            return

        # Check if the current renderer is a Paletted Raster Renderer
        renderer = terrain_layer.renderer()
        if not isinstance(renderer, QgsPalettedRasterRenderer):
            self.log_message("Selected layer does not use a Paletted/Unique Values renderer.")
            return

        # Get the classes from the renderer
        classes = renderer.classes()
        if not classes:
            self.log_message("No class data available in the renderer.")
            return

        # Populate the class table
        self.classTable.setRowCount(len(classes))
        for row, entry in enumerate(classes):
            class_id_item = QTableWidgetItem(str(entry.value))  # Use the class value
            class_id_item.setFlags(class_id_item.flags() ^ Qt.ItemIsEditable)
            self.classTable.setItem(row, 0, class_id_item)

            class_name_item = QTableWidgetItem(entry.label)  # Use the class label
            class_name_item.setFlags(class_name_item.flags() ^ Qt.ItemIsEditable)
            self.classTable.setItem(row, 1, class_name_item)

            cost_item = QTableWidgetItem("0.0")  # Default cost, editable
            cost_item.setFlags(cost_item.flags() | Qt.ItemIsEditable)
            self.classTable.setItem(row, 2, cost_item)

        self.log_message("Classification data added to the table.")

   
    def clear_logs(self):
        """Clear the log output."""
        self.log_output.clear()
            

    def run_analysis(self):
        """Main function to run the analysis by calling helper functions."""
        if not self.all_fields_valid():
            QMessageBox.warning(self, "Invalid Input", "Please fill in all required fields and ensure at least one cost is greater than 0.")
            return
        
        try:
            dem_weight, occupancy_weight = self.get_weights()
            terrain_layer, dem_layer, points_layer = self.get_layers()
            class_costs = self.get_class_costs()
            self.log_message("Starting analysis...")
            cost_result = run_r_cost(terrain_layer, points_layer)
            self.log_message("r.cost completed.")
            drain_result = run_r_drain(cost_result, points_layer)
            self.log_message("r.drain completed.")
            QgsProject.instance().addMapLayer(drain_result['output'])
            self.log_message("Least-cost path added to map.")
        except Exception as e:
            self.log_message(f"Error: {str(e)}")

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

    def get_class_costs(self):
        """Retrieve class costs from the table."""
        class_costs = {}
        for row in range(self.classTable.rowCount()):
            class_id = int(self.classTable.item(row, 0).text())
            cost = float(self.classTable.item(row, 2).text())
            class_costs[class_id] = cost
        return class_costs

    def log_message(self, message):
        """Log messages to the log output."""
        self.log_output.append(message)

    def refresh_layer_dropdown(self, combo_box, layer_type):
        """Refresh the given combo_box with all layers of the specified type in the QGIS project."""
        combo_box.blockSignals(True)  # Block signals to avoid recursion
        combo_box.clear()
        layers = QgsProject.instance().mapLayers().values()
        for layer in layers:
            if isinstance(layer, layer_type):
                combo_box.addItem(layer.name(), layer.id())

    def populate_layer_dropdowns(self):
        """Populate the dropdowns with all available layers in the project."""
        # Clear existing items
        self.terrainComboBox.clear()
        self.demComboBox.clear()
        self.pointsComboBox.clear()

        # Add placeholder items
        self.terrainComboBox.addItem("Select a terrain layer...", None)
        self.demComboBox.addItem("Select a DEM layer...", None)
        self.pointsComboBox.addItem("Select a point layer...", None)

        # Get all layers in the project
        layers = QgsProject.instance().mapLayers().values()

        # Loop through each layer in the project
        for layer in layers:
            layer_name = layer.name()
            layer_id = layer.id()

            # Check if the layer is a raster layer (for Terrain Occupancy and DEM layers)
            if isinstance(layer, QgsRasterLayer):
                self.terrainComboBox.addItem(layer_name, layer_id)
                self.demComboBox.addItem(layer_name, layer_id)
                self.log_message(f"Raster layer added to dropdowns: {layer_name}")

            # Check if the layer is a vector layer with point geometry (for Point Vector Layer)
            elif isinstance(layer, QgsVectorLayer) and layer.geometryType() == 0:
                self.pointsComboBox.addItem(layer_name, layer_id)
                self.log_message(f"Point vector layer added to dropdown: {layer_name}")

        # Log message if any dropdown is empty
        if self.terrainComboBox.count() == 1:  # Only the placeholder is present
            self.log_message("No raster layers found for Terrain Occupancy.")
        if self.demComboBox.count() == 1:  # Only the placeholder is present
            self.log_message("No raster layers found for DEM.")
        if self.pointsComboBox.count() == 1:  # Only the placeholder is present
            self.log_message("No point vector layers found for Points.")
            
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
