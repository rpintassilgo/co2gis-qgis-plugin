import os
from typing import TYPE_CHECKING
from PyQt5.QtWidgets import (
    QLabel, QComboBox, QLineEdit, QPushButton, QHBoxLayout, QFormLayout, QTableWidget, QHeaderView, QCheckBox
)
from PyQt5.QtCore import Qt
from qgis.core import QgsProject, QgsRasterLayer
from qgis import processing
from osgeo import gdal
import numpy as np
import traceback

from ..task_manager import run_in_background
from ..utils import select_output_file

if TYPE_CHECKING:
    from ..analysis_dialog import AnalysisDialog

def setup_corridors_tab(dialog: 'AnalysisDialog', layout: QFormLayout):
    # Corridor and reference selection
    dialog.corridorComboBox = QComboBox()
    layout.addRow(QLabel("Select Corridor Vector:"), dialog.corridorComboBox)
    dialog.corridorRefRasterComboBox = QComboBox()
    layout.addRow(QLabel("Select Reference Raster:"), dialog.corridorRefRasterComboBox)
    
    # Corridor buffer distance
    # Note: this can be edited if you want, if you want to consider a wider area for the corridor.
    # For example, if we set it to 100, we're saying 100 meters around the corridor will have that cheaper cost.
    dialog.corridorBufferInput = QLineEdit("25")
    layout.addRow(QLabel("Corridor Buffer Distance (meters):"), dialog.corridorBufferInput)

    # Cost inputs
    dialog.corridorPresentOffshoreInput = QLineEdit("2.7")
    layout.addRow(QLabel("Cost for corridor present offshore:"), dialog.corridorPresentOffshoreInput)
    dialog.corridorPresentOnshoreInput = QLineEdit("0.9")
    layout.addRow(QLabel("Cost for corridor present onshore:"), dialog.corridorPresentOnshoreInput)
    dialog.corridorAbsentOffshoreInput = QLineEdit("3")
    layout.addRow(QLabel("Cost for corridor absent offshore:"), dialog.corridorAbsentOffshoreInput)
    dialog.corridorAbsentOnshoreInput = QLineEdit("1")
    layout.addRow(QLabel("Cost for corridor absent onshore:"), dialog.corridorAbsentOnshoreInput)

    # Land-use selection & water-body table
    dialog.corridorLandUseComboBox = QComboBox()
    layout.addRow(QLabel("Select Land Use Layer:"), dialog.corridorLandUseComboBox)
    dialog.corridorLandUseTable = QTableWidget()
    dialog.corridorLandUseTable.setColumnCount(3)
    dialog.corridorLandUseTable.setHorizontalHeaderLabels(["Class ID", "Class Name", "Water Body"])
    dialog.corridorLandUseTable.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    layout.addRow(dialog.corridorLandUseTable)

    # Output path
    dialog.corridorOutputPath = QLineEdit()
    dialog.corridorBrowse = QPushButton("Browse")
    dialog.corridorBrowse.clicked.connect(lambda: select_output_file(dialog.corridorOutputPath, "tif"))
    path_layout = QHBoxLayout()
    path_layout.addWidget(dialog.corridorOutputPath)
    path_layout.addWidget(dialog.corridorBrowse)
    layout.addRow(path_layout)

    # Run button
    dialog.runCreateRasterFromCorridorButton = QPushButton("Create Corridors Costs Raster")
    layout.addRow(dialog.runCreateRasterFromCorridorButton)

    # Populate land-use combo
    for lyr in QgsProject.instance().mapLayers().values():
        if isinstance(lyr, QgsRasterLayer):
            dialog.corridorLandUseComboBox.addItem(lyr.name(), lyr.id())
    dialog.corridorLandUseComboBox.currentIndexChanged.connect(
        lambda: populate_corridor_land_use_table(dialog, dialog.corridorLandUseComboBox.currentData())
    )
    if dialog.corridorLandUseComboBox.count() > 0:
        populate_corridor_land_use_table(dialog, dialog.corridorLandUseComboBox.currentData())

def populate_corridor_land_use_table(dialog, layer_id):
    from qgis.core import QgsProject, QgsRasterLayer
    from PyQt5.QtWidgets import QTableWidgetItem
    dialog.corridorLandUseTable.setRowCount(0)
    lyr = QgsProject.instance().mapLayer(layer_id)
    if not isinstance(lyr, QgsRasterLayer):
        return
    rnd = lyr.renderer()
    if not hasattr(rnd, 'classes'):
        return
    for entry in rnd.classes():
        row = dialog.corridorLandUseTable.rowCount()
        dialog.corridorLandUseTable.insertRow(row)
        id_item = QTableWidgetItem(str(entry.value))
        id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)
        dialog.corridorLandUseTable.setItem(row, 0, id_item)
        name_item = QTableWidgetItem(entry.label)
        name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
        dialog.corridorLandUseTable.setItem(row, 1, name_item)
        chk = QCheckBox()
        chk.setStyleSheet("margin-left:50%;margin-right:50%;")
        dialog.corridorLandUseTable.setCellWidget(row, 2, chk)

def connect_corridors_signals(dialog: 'AnalysisDialog'):
    dialog.runCreateRasterFromCorridorButton.clicked.connect(
        lambda _: run_in_background(dialog, run_corridors_cost_creation)
    )

def run_corridors_cost_creation(dialog: 'AnalysisDialog'):
    """Create corridors cost raster with water body detection - simpler approach like crossings."""
    try:
        # Load inputs
        corridor_layer = QgsProject.instance().mapLayer(dialog.corridorComboBox.currentData())
        ref_layer = QgsProject.instance().mapLayer(dialog.corridorRefRasterComboBox.currentData())
        land_use_layer = QgsProject.instance().mapLayer(dialog.corridorLandUseComboBox.currentData())
        output_path = dialog.corridorOutputPath.text().strip()
        
        if not all([corridor_layer, ref_layer, land_use_layer, output_path]):
            raise ValueError("Select all inputs and output path.")
        
        # Parse costs and buffer distance
        present_offshore_cost = float(dialog.corridorPresentOffshoreInput.text())
        present_onshore_cost = float(dialog.corridorPresentOnshoreInput.text())
        absent_offshore_cost = float(dialog.corridorAbsentOffshoreInput.text())
        absent_onshore_cost = float(dialog.corridorAbsentOnshoreInput.text())
        buffer_distance = float(dialog.corridorBufferInput.text())
        
        # Build water IDs set from table
        water_ids = set()
        for r in range(dialog.corridorLandUseTable.rowCount()):
            item = dialog.corridorLandUseTable.item(r, 0)
            chk = dialog.corridorLandUseTable.cellWidget(r, 2)
            if item and chk and chk.isChecked():
                try:
                    water_ids.add(float(item.text()))
                except ValueError:
                    pass  # Skip invalid entries
        
        dialog.log_message(f"Water classes: {sorted(water_ids)}", "Corridors")
        if not water_ids:
            raise ValueError("No water body classes selected. Please check at least one water body class.")
        
        dialog.log_message("Creating corridors cost raster...", "Corridors")
        
        # Create corridor cost raster with buffer zones and water detection
        create_corridor_cost_raster_with_buffers(
            corridor_layer, land_use_layer, ref_layer, water_ids,
            present_offshore_cost, present_onshore_cost,
            absent_offshore_cost, absent_onshore_cost,
            buffer_distance, output_path, dialog
        )
        
        # Load result into QGIS
        layer_name = os.path.splitext(os.path.basename(output_path))[0]
        new_layer = QgsRasterLayer(output_path, layer_name)
        if not new_layer.isValid():
            raise RuntimeError("Failed to load the resulting raster layer.")
        
        QgsProject.instance().addMapLayer(new_layer)
        dialog.log_message(f"Corridors cost raster created at: {output_path}", "Corridors")
        
    except Exception as e:
        dialog.log_message(f"Corridors cost creation failed: {str(e)}", "Corridors")


def create_corridor_cost_raster_with_buffers(corridor_layer, land_use_layer, ref_layer, water_ids,
                                           present_offshore_cost, present_onshore_cost,
                                           absent_offshore_cost, absent_onshore_cost,
                                           buffer_distance, output_path, dialog):
    """Create corridor cost raster with buffer zones and proper water/land detection."""
    try:
        from osgeo import gdal
        import numpy as np
        import os
        
        dialog.log_message(f"Creating corridor buffer zones ({buffer_distance}m)...", "Corridors")
        
        # Step 1: Create buffered corridor zones
        temp_buffered_corridors = output_path.replace('.tif', '_temp_buffered_corridors.gpkg')
        
        buffer_params = {
            'INPUT': corridor_layer,
            'DISTANCE': buffer_distance,
            'SEGMENTS': 5,
            'END_CAP_STYLE': 0,  # Round
            'JOIN_STYLE': 0,  # Round
            'MITER_LIMIT': 2,
            'DISSOLVE': False,  # Dissolve overlapping buffers
            'OUTPUT': temp_buffered_corridors
        }
        
        processing.run('native:buffer', buffer_params)
        
        # Step 2: Create base cost raster with water/land detection for "absent" costs
        ref_ds = gdal.Open(ref_layer.source())
        width, height = ref_ds.RasterXSize, ref_ds.RasterYSize
        geotrans = ref_ds.GetGeoTransform()
        proj = ref_ds.GetProjection()
        
        # Step 3: Resample land use to match reference grid
        temp_lu_path = output_path.replace('.tif', '_temp_lu_aligned.tif')
        resample_params = {
            'INPUT': land_use_layer,
            'SOURCE_CRS': land_use_layer.crs(),
            'TARGET_CRS': proj,
            'RESAMPLING': 0,  # Nearest neighbor
            'NODATA': None,
            'TARGET_RESOLUTION': abs(geotrans[1]),
            'TARGET_EXTENT': f"{geotrans[0]},{geotrans[0] + width * geotrans[1]},{geotrans[3] + height * geotrans[5]},{geotrans[3]}",
            'OUTPUT': temp_lu_path,
            'EXTRA': '-co COMPRESS=LZW -co BIGTIFF=YES'
        }
        
        processing.run('gdal:warpreproject', resample_params)
        
        # Load land use data and create base cost raster
        lu_ds = gdal.Open(temp_lu_path)
        lu_data = lu_ds.GetRasterBand(1).ReadAsArray()
        
        # Create base cost raster: water = absent_offshore, land = absent_onshore
        water_pixels = np.isin(lu_data, list(water_ids))
        base_data = np.where(water_pixels, absent_offshore_cost, absent_onshore_cost).astype(np.float32)
        
        dialog.log_message(f"Base costs: {np.sum(water_pixels)} water pixels (cost: {absent_offshore_cost}), {np.sum(~water_pixels)} land pixels (cost: {absent_onshore_cost})", "Corridors")
        
        # Step 4: Create corridor buffer mask
        temp_corridor_mask = output_path.replace('.tif', '_temp_corridor_mask.tif')
        mask_params = {
            'INPUT': temp_buffered_corridors,
            'FIELD': None,
            'BURN': 1,
            'USE_Z': False,
            'UNITS': 0,
            'WIDTH': width,
            'HEIGHT': height,
            'EXTENT': f"{geotrans[0]},{geotrans[0] + width * geotrans[1]},{geotrans[3] + height * geotrans[5]},{geotrans[3]}",
            'INIT': 0,
            'DATA_TYPE': 1,  # Byte
            'OUTPUT': temp_corridor_mask
        }
        
        dialog.log_message("Rasterizing corridor buffer zones...", "Corridors")
        processing.run('gdal:rasterize', mask_params)
        
        # Load corridor mask
        mask_ds = gdal.Open(temp_corridor_mask)
        mask_data = mask_ds.GetRasterBand(1).ReadAsArray()
        
        # Step 5: Apply costs ONLY within corridor buffer zones
        corridor_pixels = mask_data == 1
        water_pixels = np.isin(lu_data, list(water_ids))
        
        # Count pixels for logging
        total_corridor_pixels = np.sum(corridor_pixels)
        offshore_pixels = np.sum(corridor_pixels & water_pixels)
        onshore_pixels = np.sum(corridor_pixels & ~water_pixels)
        
        dialog.log_message(f"Corridor buffer zones cover {total_corridor_pixels} pixels", "Corridors")
        dialog.log_message(f"  - {offshore_pixels} offshore pixels (cost: {present_offshore_cost})", "Corridors")
        dialog.log_message(f"  - {onshore_pixels} onshore pixels (cost: {present_onshore_cost})", "Corridors")
        
        if total_corridor_pixels == 0:
            dialog.log_message("WARNING: No corridor pixels found! Check buffer distance and vector layer.", "Corridors")
        
        # Apply corridor costs ONLY where corridors exist
        base_data[corridor_pixels & water_pixels] = present_offshore_cost     # Corridor + Water
        base_data[corridor_pixels & ~water_pixels] = present_onshore_cost     # Corridor + Land
        # Everything else remains cost = 1.0 (neutral)
        
        # Step 6: Write final raster
        driver = gdal.GetDriverByName('GTiff')
        out_ds = driver.Create(output_path, width, height, 1, gdal.GDT_Float32, options=['COMPRESS=LZW', 'BIGTIFF=YES'])
        out_ds.SetGeoTransform(geotrans)
        out_ds.SetProjection(proj)
        out_ds.GetRasterBand(1).WriteArray(base_data)
        
        # Cleanup
        out_ds = None
        ref_ds = None
        lu_ds = None
        mask_ds = None
        
        # Remove temp files
        for temp_file in [temp_lu_path, temp_corridor_mask, temp_buffered_corridors]:
            try:
                os.remove(temp_file)
            except:
                pass
        
        dialog.log_message("Corridor cost raster created successfully", "Corridors")
            
    except Exception as e:
        dialog.log_message(f"Corridor cost raster creation failed: {str(e)}", "Corridors")
        raise
