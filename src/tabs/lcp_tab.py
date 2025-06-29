from typing import TYPE_CHECKING
from PyQt5.QtWidgets import (
    QLabel, QComboBox, QLineEdit, QPushButton, QHBoxLayout, QFormLayout, 
    QGroupBox, QSlider, QDoubleSpinBox
)
from PyQt5.QtCore import Qt
from qgis.core import QgsProject
from qgis import processing

from ..task_manager import run_in_background
from ..utils import select_output_file, get_layer_path


if TYPE_CHECKING:
    from ..analysis_dialog import AnalysisDialog

def setup_lcp_tab(dialog: 'AnalysisDialog', layout: QFormLayout):
    """Sets up the LCP (Least Cost Path) tab."""
    # Combined Costs GroupBox
    combinedCostsGroupBox = QGroupBox()
    combinedCostsGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")
    combinedCostsLayout = QFormLayout()
    combinedCostsTitle = QLabel("Create Combined Costs Raster")
    combinedCostsTitle.setAlignment(Qt.AlignCenter)
    combinedCostsTitle.setStyleSheet("font-weight: bold; font-size: 12px;")
    combinedCostsLayout.addRow(combinedCostsTitle)
    dialog.combineLandUseDropdown = QComboBox()
    dialog.combineSlopeDropdown = QComboBox()
    dialog.combineCorridorsDropdown = QComboBox()
    dialog.combineCrossingsDropdown = QComboBox()
    combinedCostsLayout.addRow(QLabel("Select Land Use Costs Raster:"), dialog.combineLandUseDropdown)
    combinedCostsLayout.addRow(QLabel("Select Slope Costs Raster:"), dialog.combineSlopeDropdown)
    combinedCostsLayout.addRow(QLabel("Select Corridors Costs Raster:"), dialog.combineCorridorsDropdown)
    combinedCostsLayout.addRow(QLabel("Select Crossings Costs Raster:"), dialog.combineCrossingsDropdown)
    setup_weight_sliders(dialog, combinedCostsLayout)
    dialog.combinedRasterPath = QLineEdit()
    dialog.combinedRasterPath.setPlaceholderText("Choose output path for Combined Raster")
    dialog.combinedRasterBrowse = QPushButton("Browse")
    dialog.combinedRasterBrowse.clicked.connect(lambda: select_output_file(dialog.combinedRasterPath, "tif"))
    combinedFileLayout = QHBoxLayout()
    combinedFileLayout.addWidget(dialog.combinedRasterPath)
    combinedFileLayout.addWidget(dialog.combinedRasterBrowse)
    combinedCostsLayout.addRow(combinedFileLayout)
    dialog.combine_button = QPushButton("Create Combined Raster")
    combinedCostsLayout.addRow(dialog.combine_button)
    combinedCostsGroupBox.setLayout(combinedCostsLayout)
    layout.addWidget(combinedCostsGroupBox)

    # LCP GroupBox
    lcpGroupBox = QGroupBox()
    lcpGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")
    lcpPathLayout = QFormLayout()
    lcpTitle = QLabel("Create Least Cost Path")
    lcpTitle.setAlignment(Qt.AlignCenter)
    lcpTitle.setStyleSheet("font-weight: bold; font-size: 12px;")
    lcpPathLayout.addRow(lcpTitle)
    dialog.pointsComboBox = QComboBox()
    lcpPathLayout.addRow(QLabel("Select Point Vector Layer:"), dialog.pointsComboBox)
    dialog.lcpInputDropdown = QComboBox()
    lcpPathLayout.addRow(QLabel("Select Combined Raster:"), dialog.lcpInputDropdown)
    dialog.costRasterPath = QLineEdit()
    dialog.costRasterPath.setPlaceholderText("Choose output path for Cost Raster (r.cost)")
    dialog.costRasterBrowse = QPushButton("Browse")
    dialog.costRasterBrowse.clicked.connect(lambda: select_output_file(dialog.costRasterPath, "tif"))
    costFileLayout = QHBoxLayout()
    costFileLayout.addWidget(dialog.costRasterPath)
    costFileLayout.addWidget(dialog.costRasterBrowse)
    lcpPathLayout.addRow(costFileLayout)
    dialog.directionRasterPath = QLineEdit()
    dialog.directionRasterPath.setPlaceholderText("Choose output path for Direction Raster (r.cost)")
    dialog.directionRasterBrowse = QPushButton("Browse")
    dialog.directionRasterBrowse.clicked.connect(lambda: select_output_file(dialog.directionRasterPath, "tif"))
    directionFileLayout = QHBoxLayout()
    directionFileLayout.addWidget(dialog.directionRasterPath)
    directionFileLayout.addWidget(dialog.directionRasterBrowse)
    lcpPathLayout.addRow(directionFileLayout)
    dialog.drainRasterPath = QLineEdit()
    dialog.drainRasterPath.setPlaceholderText("Choose output path for Drain Raster (r.drain)")
    dialog.drainRasterBrowse = QPushButton("Browse")
    dialog.drainRasterBrowse.clicked.connect(lambda: select_output_file(dialog.drainRasterPath, "tif"))
    drainFileLayout = QHBoxLayout()
    drainFileLayout.addWidget(dialog.drainRasterPath)
    drainFileLayout.addWidget(dialog.drainRasterBrowse)
    lcpPathLayout.addRow(drainFileLayout)
    dialog.finalPath = QLineEdit()
    dialog.finalPath.setPlaceholderText("Choose output path for LCP Vector (r.to.vect)")
    dialog.finalBrowse = QPushButton("Browse")
    dialog.finalBrowse.clicked.connect(lambda: select_output_file(dialog.finalPath, "gpkg"))
    finalFileLayout = QHBoxLayout()
    finalFileLayout.addWidget(dialog.finalPath)
    finalFileLayout.addWidget(dialog.finalBrowse)
    lcpPathLayout.addRow(finalFileLayout)
    dialog.final_button = QPushButton("Run r.cost, r.drain and Convert to Vector")
    lcpPathLayout.addRow(dialog.final_button)
    lcpGroupBox.setLayout(lcpPathLayout)
    layout.addWidget(lcpGroupBox)

def connect_lcp_signals(dialog: 'AnalysisDialog'):
    """Connects signals for the LCP tab."""
    dialog.combine_button.clicked.connect(lambda: run_in_background(dialog, lambda: run_raster_combination(dialog)))
    dialog.final_button.clicked.connect(lambda: run_in_background(dialog, lambda: run_lcp_creation(dialog)))

def run_raster_combination(dialog: 'AnalysisDialog'):
    """Combine Land Use and Slope Rasters"""
    try:
        occupancy_weight = dialog.weight_spinboxes[0].value()
        dem_weight = dialog.weight_spinboxes[1].value()
        corridors_weight = dialog.weight_spinboxes[2].value()
        crossings_weight = dialog.weight_spinboxes[3].value()

        total_weight = occupancy_weight + dem_weight + corridors_weight + crossings_weight
        if abs(total_weight - 1.0) > 0.001:
            raise ValueError("The sum of all weights must be equal to 1.0.")
        if any(w < 0 for w in [occupancy_weight, dem_weight, corridors_weight, crossings_weight]):
            raise ValueError("All weights must be non-negative.")

        costs_layer = QgsProject.instance().mapLayer(dialog.combineLandUseDropdown.currentData())
        slope_layer = QgsProject.instance().mapLayer(dialog.combineSlopeDropdown.currentData())
        corridors_layer = QgsProject.instance().mapLayer(dialog.combineCorridorsDropdown.currentData())
        crossings_layer = QgsProject.instance().mapLayer(dialog.combineCrossingsDropdown.currentData())
        output_path = dialog.combinedRasterPath.text().strip()

        if not all([costs_layer, slope_layer, corridors_layer, crossings_layer, output_path]):
            raise ValueError("All raster layers and an output path must be specified.")

        dialog.log_message("Combining Cost Rasters...", "LCP")
        combine_rasters_with_qgis_raster_calculator(
            get_layer_path(costs_layer), get_layer_path(slope_layer),
            get_layer_path(corridors_layer), get_layer_path(crossings_layer),
            occupancy_weight, dem_weight, corridors_weight, crossings_weight,
            output_path
        )
        dialog.log_message(f"Combined Raster created successfully at: {output_path}", "LCP")

    except Exception as e:
        dialog.log_message(f"Combining Cost Rasters Failed: {str(e)}", "LCP")

def run_lcp_creation(dialog: 'AnalysisDialog'):
    """Generate Least Cost Path Vector"""
    try:
        points_layer = QgsProject.instance().mapLayer(dialog.pointsComboBox.currentData())
        combined_layer = QgsProject.instance().mapLayer(dialog.lcpInputDropdown.currentData())
        cost_output_path = dialog.costRasterPath.text().strip()
        direction_output_path = dialog.directionRasterPath.text().strip()
        drain_output_path = dialog.drainRasterPath.text().strip()
        vector_output_path = dialog.finalPath.text().strip()

        if not all([points_layer, combined_layer, cost_output_path, direction_output_path, drain_output_path, vector_output_path]):
            raise ValueError("All input layers and output paths must be specified.")

        dialog.log_message("Running r.cost to compute cost surface...", "LCP")
        cost_result = run_r_cost(combined_layer, points_layer, cost_output_path, direction_output_path)
        dialog.log_message(f"r.cost completed successfully.", "LCP")

        dialog.log_message("Running r.drain and converting to vector...", "LCP")
        run_r_drain_and_load(cost_result, points_layer, drain_output_path, vector_output_path)
        dialog.log_message(f"Least Cost Path Vector generated successfully at: {vector_output_path}", "LCP")

    except Exception as e:
        dialog.log_message(f"LCP Creation Process Failed: {str(e)}", "LCP")

def setup_weight_sliders(dialog: 'AnalysisDialog', layout: QFormLayout):
    """Adds sliders and spin boxes for weight input with validation feedback."""
    dialog.weight_sliders = []
    dialog.weight_spinboxes = []
    dialog._is_updating_weights = False

    labels = ["Land Use Costs Weight:", "Slope Costs Weight:", "Corridors Costs Weight:", "Crossings Costs Weight:"]
    initial_values = [0.250, 0.250, 0.250, 0.250]

    for i, label_text in enumerate(labels):
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 1000)
        slider.setValue(int(initial_values[i] * 1000))

        spinbox = QDoubleSpinBox()
        spinbox.setRange(0.0, 1.0)
        spinbox.setDecimals(3)
        spinbox.setSingleStep(0.01)
        spinbox.setValue(initial_values[i])

        dialog.weight_sliders.append(slider)
        dialog.weight_spinboxes.append(spinbox)

        row_layout = QHBoxLayout()
        row_layout.addWidget(QLabel(label_text))
        row_layout.addWidget(slider)
        row_layout.addWidget(spinbox)
        layout.addRow(row_layout)

        slider.valueChanged.connect(lambda value, s=slider: sync_and_validate_weights(dialog, changed_widget=s))
        spinbox.valueChanged.connect(lambda value, sb=spinbox: sync_and_validate_weights(dialog, changed_widget=sb))
    
    validate_weight_sum(dialog)

def sync_and_validate_weights(dialog: 'AnalysisDialog', changed_widget):
    """Syncs a slider with its spinbox and validates the total sum."""
    if dialog._is_updating_weights:
        return
    dialog._is_updating_weights = True

    if isinstance(changed_widget, QSlider):
        changed_index = dialog.weight_sliders.index(changed_widget)
        new_value = changed_widget.value()
        dialog.weight_spinboxes[changed_index].setValue(new_value / 1000.0)
    else: # QDoubleSpinBox
        changed_index = dialog.weight_spinboxes.index(changed_widget)
        new_value = changed_widget.value()
        dialog.weight_sliders[changed_index].setValue(int(new_value * 1000))

    validate_weight_sum(dialog)
    dialog._is_updating_weights = False

def validate_weight_sum(dialog: 'AnalysisDialog'):
    """Checks if the sum of weights is 1.0 and updates slider handle colors."""
    total_weight = sum(sb.value() for sb in dialog.weight_spinboxes)
    
    is_valid = abs(total_weight - 1.0) < 0.001
    color = "#5cb85c" if is_valid else "#d9534f" # Green if valid, Red if not
    style = f"QSlider::handle:horizontal {{ background-color: {color}; border-radius: 9px; }}"

    for slider in dialog.weight_sliders:
        slider.setStyleSheet(style)

def combine_rasters_with_qgis_raster_calculator(
    costs_path, slope_path, corridors_path, crossings_path,
    occupancy_weight, dem_weight, corridors_weight, crossings_weight,
    output_path
):
    """Combines rasters using QGIS Raster Calculator."""
    expression = (
        f'("{costs_path}@1" * {occupancy_weight}) + ("{slope_path}@1" * {dem_weight}) + '
        f'("{corridors_path}@1" * {corridors_weight}) + ("{crossings_path}@1" * {crossings_weight})'
    )
    
    params = {
        'EXPRESSION': expression,
        'LAYERS': [costs_path, slope_path, corridors_path, crossings_path],
        'CELLSIZE': 0,
        'EXTENT': None,
        'CRS': None,
        'OUTPUT': output_path
    }
    
    processing.run("qgis:rastercalculator", params)

def run_r_cost(input_raster, points_layer, cost_output, direction_output):
    """Runs the r.cost GRASS algorithm."""
    points_coords = [f"{p.x()},{p.y()}" for p in points_layer.getFeatures()]
    start_points_str = ",".join(points_coords)

    params = {
        'input': input_raster,
        'start_points': start_points_str,
        'output': cost_output,
        'outdir': direction_output,
        'nearest': True,
        'knight': 'I',
        'null_cost': 1.0
    }
    
    result = processing.run("grass7:r.cost", params)
    if not result or 'output' not in result:
        raise RuntimeError("r.cost processing failed to return the expected output.")
    return result['output']

def run_r_drain_and_load(cost_raster, points_layer, drain_output, vector_output):
    """Runs r.drain to create the LCP."""
    start_points_features = list(points_layer.getFeatures())
    if len(start_points_features) < 2:
        raise ValueError("Points layer must contain at least two points for r.drain.")
    
    start_point = start_points_features[0].geometry().asPoint()
    end_point = start_points_features[1].geometry().asPoint()

    params = {
        'input': cost_raster,
        'start_point': f'{start_point.x()},{start_point.y()}',
        'drain': drain_output,
        'output': vector_output,
        'points': [f'{end_point.x()},{end_point.y()}']
    }
    
    processing.run("grass7:r.drain", params)
