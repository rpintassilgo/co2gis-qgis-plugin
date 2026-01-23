from typing import TYPE_CHECKING
from PyQt5.QtWidgets import (
    QLabel, QComboBox, QLineEdit, QPushButton, QHBoxLayout, QFormLayout, 
    QGroupBox, QSlider, QDoubleSpinBox
)
from PyQt5.QtCore import Qt
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer, QgsProcessingFeedback
from qgis import processing
from osgeo import gdal
import numpy as np
import os

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
    dialog.finalPath = QLineEdit()
    dialog.finalPath.setPlaceholderText("Choose output path for LCP Vector")
    dialog.finalBrowse = QPushButton("Browse")
    dialog.finalBrowse.clicked.connect(lambda: select_output_file(dialog.finalPath, "gpkg"))
    finalFileLayout = QHBoxLayout()
    finalFileLayout.addWidget(dialog.finalPath)
    finalFileLayout.addWidget(dialog.finalBrowse)
    lcpPathLayout.addRow(finalFileLayout)
    dialog.final_button = QPushButton("Create Least Cost Path")
    lcpPathLayout.addRow(dialog.final_button)
    lcpGroupBox.setLayout(lcpPathLayout)
    layout.addWidget(lcpGroupBox)

def connect_lcp_signals(dialog: 'AnalysisDialog'):
    """Connects signals for the LCP tab."""
    dialog.combine_button.clicked.connect(lambda checked: run_in_background(dialog, run_raster_combination))
    dialog.final_button.clicked.connect(lambda checked: run_in_background(dialog, run_lcp_creation))

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
            [costs_layer, slope_layer, corridors_layer, crossings_layer],
            [occupancy_weight, dem_weight, corridors_weight, crossings_weight],
            output_path,
            dialog
        )
        dialog.log_message(f"Combined Raster created successfully at: {output_path}", "LCP")

    except Exception as e:
        dialog.log_message(f"Combining Cost Rasters Failed: {str(e)}", "LCP")

def run_lcp_creation(dialog: 'AnalysisDialog'):
    """Generate Least Cost Path Vector"""
    try:
        points_layer = QgsProject.instance().mapLayer(dialog.pointsComboBox.currentData())
        combined_layer = QgsProject.instance().mapLayer(dialog.lcpInputDropdown.currentData())
        vector_output_path = dialog.finalPath.text().strip()

        if not all([points_layer, combined_layer, vector_output_path]):
            raise ValueError("All input layers and output path must be specified.")
        
        # Create temporary paths for intermediate files
        import tempfile
        temp_dir = tempfile.mkdtemp()
        cost_output_path = os.path.join(temp_dir, "cost_surface.tif")
        direction_output_path = os.path.join(temp_dir, "direction_surface.tif")

        # Extract origin and destination
        coords = []
        for feat in points_layer.getFeatures():
            geom = feat.geometry()
            pt = geom.asPoint() if not geom.isMultipart() else geom.asMultiPoint()[0]
            coords.append((pt.x(), pt.y()))
        if len(coords) < 2:
            raise ValueError("Need at least two points (origin, destination) for LCP.")

        origin_str = f"{coords[0][0]:.6f},{coords[0][1]:.6f}"
        dest_str   = f"{coords[1][0]:.6f},{coords[1][1]:.6f}"
        dialog.log_message(f"Using origin: {origin_str}", "LCP")
        dialog.log_message(f"Using destination: {dest_str}", "LCP")

        dialog.log_message("Running r.cost to compute cost surface...", "LCP")
        dialog.log_message(f"Cost raster: {combined_layer.source()}", "LCP")
        dialog.log_message(f"Start point: {origin_str}", "LCP")
        
        cost_result = run_r_cost(combined_layer.source(), origin_str,
                                 cost_output_path, direction_output_path)
        dialog.log_message("r.cost completed successfully.", "LCP")

        dialog.log_message("Running r.drain to extract least cost path...", "LCP")
        dialog.log_message(f"Destination point: {dest_str}", "LCP")
        
        run_r_drain_and_vectorize(cost_result, dest_str, vector_output_path)
        dialog.log_message(f"Least Cost Path generated at: {vector_output_path}", "LCP")
        
        # Cleanup temporary files
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except:
            pass  # Don't fail if cleanup fails

    except Exception as e:
        dialog.log_message(f"LCP Creation Process Failed: {e}", "LCP")
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
    raster_layers: list,
    weights: list,
    output_path: str,
    dialog: 'AnalysisDialog'
) -> str:
    """Combines multiple rasters using weighted sum via resampling + numpy (handles different dimensions)."""
    if not raster_layers or not weights or len(raster_layers) != len(weights):
        raise ValueError("Invalid input: raster layers and weights must be non-empty and of equal length")

    # Debug: Check layer validity and names
    dialog.log_message("Debug: Checking input layers...", "LCP")
    for idx, layer in enumerate(raster_layers):
        dialog.log_message(f"  Layer {idx+1}: {layer.name()} - Valid: {layer.isValid()} - Source: {layer.source()}", "LCP")
        if not layer.isValid():
            raise RuntimeError(f"Invalid raster layer: {layer.name()}")

    # Step 1: Resample all rasters to match the reference raster's grid
    reference_layer = raster_layers[0]
    resampled_paths = []
    
    dialog.log_message("Step 1: Resampling rasters to match reference grid...", "LCP")
    for idx, layer in enumerate(raster_layers):
        if layer == reference_layer:
            # Reference layer doesn't need resampling
            resampled_paths.append(layer.source())
            continue
            
        # Resample to match reference
        resampled_path = os.path.join(os.path.dirname(output_path), f'_resampled_{idx}.tif')
        params = {
            'INPUT': layer,
            'SOURCE_CRS': layer.crs(),
            'TARGET_CRS': reference_layer.crs(),
            'RESAMPLING': 0,  # Nearest neighbor
            'NODATA': None,
            'TARGET_RESOLUTION': reference_layer.rasterUnitsPerPixelX(),
            'OUTPUT': resampled_path
        }
        
        # Set extent to match reference
        extent = reference_layer.extent()
        params['TARGET_EXTENT'] = f"{extent.xMinimum()},{extent.xMaximum()},{extent.yMinimum()},{extent.yMaximum()}"
        
        dialog.log_message(f"  Resampling {layer.name()}...", "LCP")
        result = processing.run('gdal:warpreproject', params)
        if result and 'OUTPUT' in result:
            resampled_paths.append(result['OUTPUT'])
        else:
            raise RuntimeError(f"Failed to resample {layer.name()}")
    
    # Step 2: Combine resampled rasters using numpy
    dialog.log_message("Step 2: Combining resampled rasters...", "LCP")
    
    # Read reference raster to get dimensions
    ref_ds = gdal.Open(reference_layer.source())
    width = ref_ds.RasterXSize
    height = ref_ds.RasterYSize
    geotrans = ref_ds.GetGeoTransform()
    proj = ref_ds.GetProjection()
    
    # Create output array
    output_data = np.zeros((height, width), dtype=np.float32)
    
    # Process each resampled raster
    for idx, (resampled_path, weight) in enumerate(zip(resampled_paths, weights)):
        ds = gdal.Open(resampled_path)
        if not ds:
            raise RuntimeError(f"Could not open resampled raster: {resampled_path}")
        
        # Read data and normalize to 0-1 range before weighting
        data = ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
        
        # Handle nodata values
        nodata = ds.GetRasterBand(1).GetNoDataValue()
        if nodata is not None:
            mask = data != nodata
            if np.any(mask):
                # Normalize only valid data to 0-1 range
                valid_data = data[mask]
                min_val, max_val = np.min(valid_data), np.max(valid_data)
                if max_val > min_val:
                    data[mask] = (valid_data - min_val) / (max_val - min_val)
                else:
                    data[mask] = 0.5  # constant value case
        else:
            # Normalize entire array
            min_val, max_val = np.min(data), np.max(data)
            if max_val > min_val:
                data = (data - min_val) / (max_val - min_val)
            else:
                data = np.full_like(data, 0.5)
        
        # Add weighted contribution
        output_data += data * weight
        ds = None
    
    # Post-process the combined cost surface for better LCP results
    # Scale by cell resolution to improve r.drain performance
    cell_size = abs(geotrans[1])  # pixel width
    output_data = output_data * cell_size
    
    # Ensure minimum cost > 0 (avoid zero costs that can cause issues)
    output_data = np.maximum(output_data, 0.001)
    
    # Write final output
    driver = gdal.GetDriverByName('GTiff')
    out_ds = driver.Create(output_path, width, height, 1, gdal.GDT_Float32, options=['COMPRESS=LZW'])
    out_ds.SetGeoTransform(geotrans)
    out_ds.SetProjection(proj)
    out_ds.GetRasterBand(1).WriteArray(output_data)
    out_ds = None
    ref_ds = None
    
    # Clean up temporary files
    for idx, resampled_path in enumerate(resampled_paths):
        if idx > 0 and resampled_path != reference_layer.source():  # Skip reference layer
            try:
                os.remove(resampled_path)
            except:
                pass
    
    # Load the result into QGIS
    new_layer = QgsRasterLayer(output_path, "Combined Costs")
    if new_layer.isValid():
        QgsProject.instance().addMapLayer(new_layer)
        dialog.log_message("Successfully created and loaded combined cost raster", "LCP")
        return output_path
    else:
        raise RuntimeError("Failed to load the combined cost raster")

def run_r_cost(input_raster: str,
               start_coordinates: str,
               cost_output: str,
               direction_output: str) -> dict:
    """
    Runs the r.cost GRASS algorithm using start coordinates.
    """
    # 1) Make sure output folders exist
    for path in (cost_output, direction_output):
        d = os.path.dirname(path)
        if d and not os.path.exists(d):
            os.makedirs(d, exist_ok=True)

    # 2) Read the raster to set the GRASS region
    rlayer = QgsRasterLayer(input_raster, "temp")
    if not rlayer.isValid():
        raise RuntimeError(f"Invalid cost raster: {input_raster}")
    ext = rlayer.extent()
    region = f"{ext.xMinimum()},{ext.xMaximum()},{ext.yMinimum()},{ext.yMaximum()}"

    # 3) Build parameters for r.cost - use start_points for the origin
    params = {
        'input':                  input_raster,
        'start_coordinates': start_coordinates,    # Use start_points for r.cost
        '-n':                     True,                 # Use Knight's move
        'max_cost':               0,                    # no maximum cost
        'memory':                 2000,
        'output':                 cost_output,
        'outdir':                 direction_output,
        'GRASS_REGION_PARAMETER': region,
        'GRASS_REGION_CELLSIZE_PARAMETER': 0
    }

    # 4) Run r.cost to generate cost accumulation and direction surfaces
    result = processing.run("grass7:r.cost", params)
    
    if not result:
        raise RuntimeError("r.cost processing failed")

    # 5) Return the result for downstream use
    return {
        'output': cost_output,
        'outdir': direction_output
    }


def run_r_drain_and_vectorize(cost_result: dict,
                              dest_coord: str,
                              vector_output: str) -> None:
    """
    Simple LCP extraction using r.drain → r.to.vect.
    Proven to work reliably based on successful logs.
    """
    import os, tempfile, shutil
    from qgis.core import QgsProject, QgsVectorLayer
    from qgis import processing

    out_dir = os.path.dirname(vector_output)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    temp_dir = tempfile.mkdtemp()
    
    # r.drain needs the accumulation raster (cost_result['output']) and start from DESTINATION.
    # It traces the steepest descent (lowest cost) to the source encoded by r.cost.
    accum_path = cost_result['output']
    direction_path = cost_result['outdir']
    
    if not os.path.exists(accum_path):
        raise RuntimeError(f"Cost accumulation raster not found: {accum_path}")
    if not os.path.exists(direction_path):
        raise RuntimeError(f"Direction raster not found: {direction_path}")

    # r.drain → raster path, then r.to.vect lines to GPKG
    drain_out = os.path.join(temp_dir, "drain_path.tif")
    
    # Run r.drain from destination to trace back to origin
    # CRITICAL: Must pass direction raster from r.cost to follow the cost path correctly
    processing.run("grass7:r.drain", {
        'input': accum_path,
        'direction': direction_path,
        'start_coordinates': dest_coord,
        'output': drain_out,
        'GRASS_REGION_CELLSIZE_PARAMETER': 0
    })

    # Convert raster path to vector lines
    processing.run("grass7:r.to.vect", {
        'input': drain_out,
        'type': 0, # line
        'output': vector_output
    })

    # Load the resulting vector
    layer = QgsVectorLayer(vector_output, "Least Cost Path", "ogr")
    if not layer.isValid():
        raise RuntimeError(f"Failed to load LCP vector: {vector_output}")
    QgsProject.instance().addMapLayer(layer)

    # Log success
    try:
        # Try to access dialog for logging if available in scope
        import inspect
        frame = inspect.currentframe()
        while frame:
            if 'dialog' in frame.f_locals:
                dialog = frame.f_locals['dialog']
                dialog.log_message("LCP created using: r.drain → r.to.vect", "LCP")
                break
            frame = frame.f_back
    except:
        pass  # Silent fallback if logging not available
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)



