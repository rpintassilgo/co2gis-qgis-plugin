from typing import TYPE_CHECKING
from PyQt5.QtWidgets import (
    QLabel, QComboBox, QLineEdit, QPushButton, QHBoxLayout, QFormLayout, 
    QGroupBox
)
from PyQt5.QtCore import Qt
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer, QgsProcessingFeedback
from qgis import processing
from osgeo import gdal
import numpy as np
import os
import gc

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
    dialog.combineNRasterDropdown = QComboBox()
    combinedCostsLayout.addRow(QLabel("Select Land Use Costs Raster (F<sub>lu</sub>):"), dialog.combineLandUseDropdown)
    combinedCostsLayout.addRow(QLabel("Select Slope Costs Raster (F<sub>s</sub>):"), dialog.combineSlopeDropdown)
    combinedCostsLayout.addRow(QLabel("Select Corridors Costs Raster (F<sub>c</sub>):"), dialog.combineCorridorsDropdown)
    combinedCostsLayout.addRow(QLabel("Select Crossings Costs Raster (F<sub>ci</sub>):"), dialog.combineCrossingsDropdown)
    combinedCostsLayout.addRow(QLabel("Select Number of Crossings Raster (N):"), dialog.combineNRasterDropdown)
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
    """Combine Cost Rasters using COMET formula with N factor"""
    try:
        # Load all layers
        costs_layer = QgsProject.instance().mapLayer(dialog.combineLandUseDropdown.currentData())
        slope_layer = QgsProject.instance().mapLayer(dialog.combineSlopeDropdown.currentData())
        corridors_layer = QgsProject.instance().mapLayer(dialog.combineCorridorsDropdown.currentData())
        crossings_layer = QgsProject.instance().mapLayer(dialog.combineCrossingsDropdown.currentData())
        N_layer = QgsProject.instance().mapLayer(dialog.combineNRasterDropdown.currentData())
        output_path = dialog.combinedRasterPath.text().strip()

        if not output_path:
            raise ValueError("Output path must be specified.")

        dialog.log_message("Combining Cost Rasters using COMET formula: Fc × Fs × [Flu × (1-0.1N) + 0.1N × Fci]", "LCP")
        combine_rasters_with_comet_formula(
            costs_layer, slope_layer, corridors_layer, crossings_layer, N_layer,
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

def combine_rasters_with_comet_formula(
    land_use_layer, slope_layer, corridors_layer, crossings_layer, N_layer,
    output_path: str,
    dialog: 'AnalysisDialog'
) -> str:
    """
    Combines rasters using COMET formula: Fc × Fs × [Flu × (1-0.1N) + 0.1N × Fci]
    
    Parameters:
        land_use_layer: Flu (land use costs)
        slope_layer: Fs (slope costs)
        corridors_layer: Fc (corridor costs)
        crossings_layer: Fci (crossing costs)
        N_layer: N (number of infrastructure crossings per cell)
        
    Any layer can be None - will be treated as constant 1.0 (neutral)
    N is capped at 10 to avoid negative Flu coefficients and numerical instability
    """
    from qgis.core import QgsRectangle
    
    # Collect valid layers
    all_layers = []
    layer_names = ['Land Use (Flu)', 'Slope (Fs)', 'Corridors (Fc)', 'Crossings (Fci)', 'N (count)']
    layer_map = {}
    
    for idx, (layer, name) in enumerate(zip(
        [land_use_layer, slope_layer, corridors_layer, crossings_layer, N_layer],
        layer_names
    )):
        if layer and layer.isValid():
            all_layers.append(layer)
            layer_map[name] = idx
            dialog.log_message(f"  {name}: {layer.name()} - Valid", "LCP")
        else:
            dialog.log_message(f"  ⚠️ {name}: Not selected - will use constant 1.0", "LCP")
    
    if not all_layers:
        raise ValueError("At least one cost raster must be provided!")
    
    # Calculate common extent
    dialog.log_message("Step 1: Calculating common extent...", "LCP")
    common_extent = all_layers[0].extent()
    for layer in all_layers[1:]:
        common_extent = common_extent.intersect(layer.extent())
    
    if common_extent.isEmpty():
        raise ValueError("No common extent found - rasters do not overlap!")
    
    # Use first valid layer as reference for resolution
    reference_layer = all_layers[0]
    ref_resolution = reference_layer.rasterUnitsPerPixelX()
    dialog.log_message(f"Using resolution: {ref_resolution:.2f}m from {reference_layer.name()}", "LCP")
    
    # Resample all valid layers
    dialog.log_message("Step 2: Resampling rasters...", "LCP")
    resampled_data = {}
    
    valid_layers_to_resample = [(layer, name) for layer, name in zip(
        [land_use_layer, slope_layer, corridors_layer, crossings_layer, N_layer],
        layer_names
    ) if layer and layer.isValid()]
    
    total_layers = len(valid_layers_to_resample)
    current_layer = 0
    
    for layer, name in valid_layers_to_resample:
        current_layer += 1
        dialog.log_message(f"  Resampling {current_layer}/{total_layers}: {name}...", "LCP")
        
        resampled_path = os.path.join(os.path.dirname(output_path), f'_resampled_{name.replace(" ", "_")}.tif')
        
        params = {
            'INPUT': layer,
            'SOURCE_CRS': layer.crs(),
            'TARGET_CRS': reference_layer.crs(),
            'RESAMPLING': 0,
            'NODATA': None,
            'TARGET_RESOLUTION': ref_resolution,
            'TARGET_EXTENT': f"{common_extent.xMinimum()},{common_extent.xMaximum()},{common_extent.yMinimum()},{common_extent.yMaximum()}",
            'OUTPUT': resampled_path,
            'EXTRA': '-co COMPRESS=LZW -co BIGTIFF=YES'
        }
        
        result = processing.run('gdal:warpreproject', params)
        
        if result and 'OUTPUT' in result:
            ds = gdal.Open(result['OUTPUT'])
            if ds is None:
                raise RuntimeError(f"Failed to open resampled raster for {layer.name()}")
                
            band = ds.GetRasterBand(1)
            data = band.ReadAsArray().astype(np.float32)
            
            # Get dimensions from first raster
            if not resampled_data:
                width = ds.RasterXSize
                height = ds.RasterYSize
                geotrans = ds.GetGeoTransform()
                proj = ds.GetProjection()
                resampled_data['_meta'] = {'width': width, 'height': height, 'geotrans': geotrans, 'proj': proj}
                dialog.log_message(f"  Target grid: {width}x{height} pixels ({width*height:,} total cells)", "LCP")
            
            resampled_data[name] = data
            
            # Properly close GDAL dataset
            band = None
            ds = None
            
            # Clean up temp file
            try:
                if os.path.exists(result['OUTPUT']):
                    os.remove(result['OUTPUT'])
            except Exception as cleanup_error:
                dialog.log_message(f"  ⚠️ Could not delete temp file: {cleanup_error}", "LCP")
        else:
            raise RuntimeError(f"Failed to resample {layer.name()}")
    
    # Get dimensions
    meta = resampled_data['_meta']
    width, height = meta['width'], meta['height']
    geotrans, proj = meta['geotrans'], meta['proj']
    
    dialog.log_message("Step 3: Applying COMET formula...", "LCP")
    
    # Create arrays with default value 1.0 for missing layers
    Flu = resampled_data.get('Land Use (Flu)', np.ones((height, width), dtype=np.float32))
    Fs = resampled_data.get('Slope (Fs)', np.ones((height, width), dtype=np.float32))
    Fc = resampled_data.get('Corridors (Fc)', np.ones((height, width), dtype=np.float32))
    Fci = resampled_data.get('Crossings (Fci)', np.ones((height, width), dtype=np.float32))
    N = resampled_data.get('N (count)', np.ones((height, width), dtype=np.float32))
    
    # Log warnings for missing layers
    if 'Land Use (Flu)' not in resampled_data:
        dialog.log_message("  ⚠️ Land Use (Flu) not selected - assuming Flu=1.0 (neutral)", "LCP")
    if 'Slope (Fs)' not in resampled_data:
        dialog.log_message("  ⚠️ Slope (Fs) not selected - assuming Fs=1.0 (neutral)", "LCP")
    if 'Corridors (Fc)' not in resampled_data:
        dialog.log_message("  ⚠️ Corridors (Fc) not selected - assuming Fc=1.0 (neutral)", "LCP")
    if 'Crossings (Fci)' not in resampled_data:
        dialog.log_message("  ⚠️ Crossings (Fci) not selected - assuming Fci=1.0 (neutral)", "LCP")
    if 'N (count)' not in resampled_data:
        dialog.log_message("  ⚠️ N (count) not selected - assuming N=1.0 (one infrastructure per cell)", "LCP")
    
    # Log value ranges
    dialog.log_message(f"  Flu range: [{np.min(Flu):.2f}, {np.max(Flu):.2f}]", "LCP")
    dialog.log_message(f"  Fs range: [{np.min(Fs):.2f}, {np.max(Fs):.2f}]", "LCP")
    dialog.log_message(f"  Fc range: [{np.min(Fc):.2f}, {np.max(Fc):.2f}]", "LCP")
    dialog.log_message(f"  Fci range: [{np.min(Fci):.2f}, {np.max(Fci):.2f}]", "LCP")
    dialog.log_message(f"  N range (before cap): [{np.min(N):.2f}, {np.max(N):.2f}]", "LCP")
    
    # Cap N at 10 (critical for formula stability)
    N_capped = np.minimum(N, 10)
    
    if np.max(N) > 10:
        num_capped = np.sum(N > 10)
        dialog.log_message(f"  ⚠️ {num_capped:,} pixels had N > 10 and were capped to 10", "LCP")
    
    dialog.log_message(f"  N range (after cap): [{np.min(N_capped):.2f}, {np.max(N_capped):.2f}]", "LCP")
    
    # Apply COMET formula: Fc × Fs × [Flu × (1 - 0.1N) + 0.1N × Fci]
    dialog.log_message(f"  Calculating formula for {width*height:,} pixels...", "LCP")
    inner_term = Flu * (1 - 0.1 * N_capped) + 0.1 * N_capped * Fci
    output_data = Fc * Fs * inner_term
    dialog.log_message(f"  ✓ Formula applied successfully", "LCP")
    
    # Log final cost range
    dialog.log_message(f"  Combined cost range: [{np.min(output_data):.2f}, {np.max(output_data):.2f}]", "LCP")
    
    # Ensure minimum cost > 0 (avoid issues with r.drain)
    output_data = np.maximum(output_data, 0.001)
    
    # Write final output
    dialog.log_message("Step 4: Writing output raster...", "LCP")
    driver = gdal.GetDriverByName('GTiff')
    out_ds = driver.Create(output_path, width, height, 1, gdal.GDT_Float32, options=['COMPRESS=LZW', 'BIGTIFF=YES'])
    out_ds.SetGeoTransform(geotrans)
    out_ds.SetProjection(proj)
    out_band = out_ds.GetRasterBand(1)
    out_band.WriteArray(output_data)
    out_band.FlushCache()
    out_band = None
    out_ds.FlushCache()
    out_ds = None
    dialog.log_message(f"  ✓ Raster written to: {os.path.basename(output_path)}", "LCP")
    
    # Force memory cleanup
    dialog.log_message("  Cleaning up memory...", "LCP")
    output_data = None
    Flu = None
    Fs = None
    Fc = None
    Fci = None
    N = None
    N_capped = None
    inner_term = None
    resampled_data = None
    gc.collect()
    
    dialog.log_message("Step 5: Loading result into QGIS...", "LCP")
    # Load result into QGIS
    layer_name = os.path.splitext(os.path.basename(output_path))[0]
    new_layer = QgsRasterLayer(output_path, layer_name)
    if new_layer.isValid():
        QgsProject.instance().addMapLayer(new_layer)
        dialog.log_message("✓ Successfully created combined cost raster using COMET formula", "LCP")
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
    layer_name = os.path.splitext(os.path.basename(vector_output))[0]
    layer = QgsVectorLayer(vector_output, layer_name, "ogr")
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



