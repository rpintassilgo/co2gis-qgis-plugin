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
    """Create two masks (corridor & water) aligned to reference, then combine costs."""
    try:
        # Load inputs
        vec = QgsProject.instance().mapLayer(dialog.corridorComboBox.currentData())
        ref = QgsProject.instance().mapLayer(dialog.corridorRefRasterComboBox.currentData())
        lu  = QgsProject.instance().mapLayer(dialog.corridorLandUseComboBox.currentData())
        out = dialog.corridorOutputPath.text().strip()
        if not all([vec, ref, lu, out]):
            raise ValueError("Select all inputs and output path.")
        
        # Parse costs
        pres_off = float(dialog.corridorPresentOffshoreInput.text())
        pres_on  = float(dialog.corridorPresentOnshoreInput.text())
        abs_off  = float(dialog.corridorAbsentOffshoreInput.text())
        abs_on   = float(dialog.corridorAbsentOnshoreInput.text())
        
        # Build water IDs set
        water_ids = set()
        for r in range(dialog.corridorLandUseTable.rowCount()):
            item = dialog.corridorLandUseTable.item(r, 0)
            chk  = dialog.corridorLandUseTable.cellWidget(r, 2)
            if item and chk and chk.isChecked():
                water_ids.add(float(item.text()))
        dialog.log_message(f"Water classes: {sorted(water_ids)}", "Corridors")
        
        # Common params
        width, height = ref.width(), ref.height()
        extent = ref.extent()
        ref_ds = gdal.Open(ref.source())
        geotrans = ref_ds.GetGeoTransform()
        proj = ref_ds.GetProjection()
        
        # 1) Corridor mask (0/1)
        mask_path = os.path.join(os.path.dirname(out), '_mask_corridor.tif')
        mask_params = {
            'INPUT': vec,
            'FIELD': None,
            'BURN': 1,
            'USE_Z': False,
            'UNITS': 0,
            'WIDTH': width,
            'HEIGHT': height,
            'EXTENT': extent,
            'INIT': 0,
            'DATA_TYPE': 1,  # Byte
            'OUTPUT': mask_path
        }
        processing.run('gdal:rasterize', mask_params)
        m_ds = gdal.Open(mask_path)
        m_arr = m_ds.GetRasterBand(1).ReadAsArray()
        
        # 2) Water mask: resample land use raster to reference grid
        lu_path = os.path.join(os.path.dirname(out), '_lu_resampled.tif')
        gdal.Warp(
            lu_path,
            lu.source(),
            format='GTiff',
            outputBounds=(geotrans[0], geotrans[3] + height * geotrans[5], geotrans[0] + width * geotrans[1], geotrans[3]),
            width=width,
            height=height,
            dstSRS=proj,
            resampleAlg='near',
            outputType=gdal.GDT_Float32
        )
        lu_ds = gdal.Open(lu_path)
        lu_arr = lu_ds.GetRasterBand(1).ReadAsArray()
        
        # Build water mask array (1 for water, 0 otherwise)
        w_arr = np.isin(lu_arr, list(water_ids)).astype(np.uint8)
        
        # 3) Combine
        out_arr = np.zeros_like(m_arr, dtype=np.float32)
        out_arr[(m_arr==1)&(w_arr==1)]  = pres_off
        out_arr[(m_arr==1)&(w_arr==0)]  = pres_on
        out_arr[(m_arr==0)&(w_arr==1)]  = abs_off
        out_arr[(m_arr==0)&(w_arr==0)]  = abs_on
        
        # 4) Write final
        drv = gdal.GetDriverByName('GTiff')
        o_ds = drv.Create(out,
                          width,
                          height,
                          1,
                          gdal.GDT_Float32,
                          options=['COMPRESS=LZW'])
        o_ds.SetGeoTransform(geotrans)
        o_ds.SetProjection(proj)
        o_ds.GetRasterBand(1).WriteArray(out_arr)
        o_ds = None
        
        # Cleanup
        m_ds, lu_ds, ref_ds = None, None, None
        os.remove(mask_path)
        os.remove(lu_path)
        
        # Load
        layer = QgsRasterLayer(out, 'Corridors Costs')
        QgsProject.instance().addMapLayer(layer)
        dialog.log_message(f"Corridors cost raster created: {out}", "Corridors")
    except Exception as e:
        dialog.log_message(f"Error: {e}", "Corridors")
        dialog.log_message(traceback.format_exc(), "Corridors")
