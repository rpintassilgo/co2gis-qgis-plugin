from typing import TYPE_CHECKING
from PyQt5.QtWidgets import (
    QVBoxLayout, QLabel, QComboBox, QTableWidget, QLineEdit, QPushButton, QCheckBox,
    QFormLayout, QHeaderView, QTextEdit, QTabWidget, QGroupBox, QHBoxLayout, QFileDialog
)
from PyQt5.QtCore import Qt
from qgis.core import QgsProject, QgsUnitTypes

if TYPE_CHECKING:
    from . import StepByStepDialog

def setup_ui(dialog: 'StepByStepDialog'):
    """Set up the UI for StepByStepDialog."""
    dialog.setWindowTitle("Step-by-Step Analysis")
    dialog.setGeometry(0, 0, 2100, 900)

    main_layout = QVBoxLayout()
    columns_layout = QHBoxLayout()
    left_layout = QVBoxLayout()
    middle_layout = QVBoxLayout()
    right_layout = QVBoxLayout()
    
    columns_layout.addLayout(left_layout)  # Add left column to main columns layout
    columns_layout.addLayout(middle_layout)  # Add middle column to main columns layout
    columns_layout.addLayout(right_layout)  # Add right column to main columns layout

    main_layout.addLayout(columns_layout)  # Add the columns to the main layout

    ############ STEP 1: Select Start & End Points ############
    pointsGroupBox = QGroupBox()
    pointsGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")
    pointsLayout = QFormLayout()
    
    pointsTitle = QLabel("Select Start and End Points")
    pointsTitle.setAlignment(Qt.AlignCenter)  # Center the label text
    pointsTitle.setStyleSheet("font-weight: bold; font-size: 12px;")  # Make text bold
    pointsLayout.addRow(pointsTitle)

    dialog.pointsComboBox = QComboBox()
    pointsLayout.addRow(QLabel("Select Point Vector Layer Containing Start and End Points:")) 
    pointsLayout.addRow(dialog.pointsComboBox) 

    pointsGroupBox.setLayout(pointsLayout)
    left_layout.addWidget(pointsGroupBox)

    ############ STEP 2: Select DEM Layer & Create Slope Raster ############
    demGroupBox = QGroupBox()
    demGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")
    demLayout = QFormLayout()
    
    demTitle = QLabel("Select DEM Layer and Create Slope Raster")
    demTitle.setAlignment(Qt.AlignCenter)  # Center the label text
    demTitle.setStyleSheet("font-weight: bold; font-size: 12px;")  # Make text bold
    demLayout.addRow(demTitle)

    dialog.demComboBox = QComboBox()
    demLayout.addRow(QLabel("Select DEM Layer:"))
    demLayout.addRow(dialog.demComboBox)
    
    # File path selection
    dialog.slopeRasterPath = QLineEdit()
    dialog.slopeRasterPath.setPlaceholderText("Choose output path for Slope Raster")
    dialog.slopeRasterBrowse = QPushButton("Browse")
    dialog.slopeRasterBrowse.clicked.connect(lambda: select_output_file(dialog.slopeRasterPath, "tif"))
    
    fileLayout = QHBoxLayout()
    fileLayout.addWidget(dialog.slopeRasterPath)
    fileLayout.addWidget(dialog.slopeRasterBrowse)
    demLayout.addRow(fileLayout)

    dialog.create_slope_button = QPushButton("Create Slope Raster from DEM")
    demLayout.addWidget(dialog.create_slope_button)

    demGroupBox.setLayout(demLayout)
    left_layout.addWidget(demGroupBox)

    ############ STEP 3: Select Land Use Layer, Get Classes & Create Costs Raster ############
    landUseGroupBox = QGroupBox()
    landUseGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")
    landUseLayout = QFormLayout()
    
    landCostsTitle = QLabel("Select Land Use Layer, Apply Costs to Classes and Create Costs Raster")
    landCostsTitle.setAlignment(Qt.AlignCenter)  # Center the label text
    landCostsTitle.setStyleSheet("font-weight: bold; font-size: 12px;")  # Make text bold
    landUseLayout.addRow(landCostsTitle)

    dialog.terrainComboBox = QComboBox()
    landUseLayout.addRow(QLabel("Select Land Use Layer:"))
    landUseLayout.addRow(dialog.terrainComboBox)

    dialog.classify_button = QPushButton("Get Classes")
    landUseLayout.addWidget(dialog.classify_button)

    # Land Use Classes Table
    dialog.classTable = QTableWidget()
    dialog.classTable.setColumnCount(3)
    dialog.classTable.setHorizontalHeaderLabels(["Class ID", "Class Name", "Cost"])
    dialog.classTable.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    landUseLayout.addRow(QLabel("Land Use Classes Costs:"))
    landUseLayout.addWidget(dialog.classTable)
    
    # File path selection
    dialog.costsRasterPath = QLineEdit()
    dialog.costsRasterPath.setPlaceholderText("Choose output path for Costs Raster")
    dialog.costsRasterBrowse = QPushButton("Browse")
    dialog.costsRasterBrowse.clicked.connect(lambda: select_output_file(dialog.costsRasterPath, "tif"))
    
    costsfileLayout = QHBoxLayout()
    costsfileLayout.addWidget(dialog.costsRasterPath)
    costsfileLayout.addWidget(dialog.costsRasterBrowse)
    landUseLayout.addRow(costsfileLayout)

    dialog.create_land_use_costs_button = QPushButton("Create Land Use Costs Raster")
    landUseLayout.addWidget(dialog.create_land_use_costs_button)

    landUseGroupBox.setLayout(landUseLayout)
    left_layout.addWidget(landUseGroupBox)

    ############ STEP 4: Combine Rasters (Land Use & Slope) ############
    combineGroupBox = QGroupBox()
    combineGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")
    combineLayout = QFormLayout()
    
    combineTitle = QLabel("Combine Rasters (Land Use and Slope)")
    combineTitle.setAlignment(Qt.AlignCenter)  # Center the label text
    combineTitle.setStyleSheet("font-weight: bold; font-size: 12px;")  # Make text bold
    combineLayout.addRow(combineTitle)
    
    infoText = QLabel(
        "ⓘ If the input rasters have different resolutions, QGIS will automatically resample them using the nearest neighbor algorithm."
    )
    infoText.setStyleSheet("color: lightgrey; font-size: 11px;")  # Make text bold
    combineLayout.addRow(infoText)

    dialog.step3LandUseDropdown = QComboBox()
    dialog.step3SlopeDropdown = QComboBox()
    combineLayout.addRow(QLabel("Select Land Use Costs Raster:"), dialog.step3LandUseDropdown)
    combineLayout.addRow(QLabel("Select Slope Raster:"), dialog.step3SlopeDropdown)

    # Weights Input Fields
    dialog.landUseCostWeightInput = QLineEdit()
    dialog.landUseCostWeightInput.setPlaceholderText("Enter Land Use Costs Weight")
    dialog.slopeRasterWeightInput = QLineEdit()
    dialog.slopeRasterWeightInput.setPlaceholderText("Enter Slope Weight")

    combineLayout.addRow(QLabel("Land Use Costs Weight:"), dialog.landUseCostWeightInput)
    combineLayout.addRow(QLabel("Slope Weight:"), dialog.slopeRasterWeightInput)
    
    # File path selection
    dialog.combinedRasterPath = QLineEdit()
    dialog.combinedRasterPath.setPlaceholderText("Choose output path for Combined Raster")
    dialog.combinedRasterBrowse = QPushButton("Browse")
    dialog.combinedRasterBrowse.clicked.connect(lambda: select_output_file(dialog.combinedRasterPath, "tif"))
    
    combinedfileLayout = QHBoxLayout()
    combinedfileLayout.addWidget(dialog.combinedRasterPath)
    combinedfileLayout.addWidget(dialog.combinedRasterBrowse)
    combineLayout.addRow(combinedfileLayout)

    dialog.combine_button = QPushButton("Combine Rasters")
    combineLayout.addRow(dialog.combine_button)

    combineGroupBox.setLayout(combineLayout)
    middle_layout.addWidget(combineGroupBox)

    ############ STEP 5: Select Combined Raster & Clip ############
    clipGroupBox = QGroupBox()
    clipGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")
    clipLayout = QFormLayout()
    
    clipTitle = QLabel("Select Raster and Create Clipped Raster")
    clipTitle.setAlignment(Qt.AlignCenter)  # Center the label text
    clipTitle.setStyleSheet("font-weight: bold; font-size: 12px;")  # Make text bold
    clipLayout.addRow(clipTitle)

    dialog.step4Dropdown = QComboBox()
    clipLayout.addRow(QLabel("Select Raster To Clip:"))
    clipLayout.addRow(dialog.step4Dropdown)
    
    # Checkbox to Copy Symbology
    dialog.copySymbologyCheckbox = QCheckBox("Copy Symbology to Clipped Raster")
    dialog.copySymbologyCheckbox.setChecked(False)  # Default checked
    clipLayout.addRow(dialog.copySymbologyCheckbox)
    
    # File path selection
    dialog.clippedRasterPath = QLineEdit()
    dialog.clippedRasterPath.setPlaceholderText("Choose output path for Clipped Raster")
    dialog.clippedRasterBrowse = QPushButton("Browse")
    dialog.clippedRasterBrowse.clicked.connect(lambda: select_output_file(dialog.clippedRasterPath, "tif"))
    
    combinedfileLayout = QHBoxLayout()
    combinedfileLayout.addWidget(dialog.clippedRasterPath)
    combinedfileLayout.addWidget(dialog.clippedRasterBrowse)
    clipLayout.addRow(combinedfileLayout)

    dialog.clip_button = QPushButton("Clip Raster to Area")
    clipLayout.addWidget(dialog.clip_button)

    clipGroupBox.setLayout(clipLayout)
    right_layout.addWidget(clipGroupBox)

    ############ STEP 6: Select Clipped Combined Raster & Run r.cost, r.drain ############
    finalStepGroupBox = QGroupBox()
    finalStepGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")
    finalStepLayout = QFormLayout()

    finalTitle = QLabel("Create Least Cost Path Vector from Entire or Clipped Raster")
    finalTitle.setAlignment(Qt.AlignCenter)
    finalTitle.setStyleSheet("font-weight: bold; font-size: 12px;")
    finalStepLayout.addRow(finalTitle)

    dialog.step5Dropdown = QComboBox()
    finalStepLayout.addRow(QLabel("Select Combined Raster:"))
    finalStepLayout.addRow(dialog.step5Dropdown)

    # Cost Raster Output Path
    dialog.costRasterPath = QLineEdit()
    dialog.costRasterPath.setPlaceholderText("Choose output path for Cost Raster (r.cost)")
    dialog.costRasterBrowse = QPushButton("Browse")
    dialog.costRasterBrowse.clicked.connect(lambda: select_output_file(dialog.costRasterPath, "tif"))

    costFileLayout = QHBoxLayout()
    costFileLayout.addWidget(dialog.costRasterPath)
    costFileLayout.addWidget(dialog.costRasterBrowse)
    finalStepLayout.addRow(costFileLayout)

    # Direction Raster Output Path
    dialog.directionRasterPath = QLineEdit()
    dialog.directionRasterPath.setPlaceholderText("Choose output path for Direction Raster (r.cost)")
    dialog.directionRasterBrowse = QPushButton("Browse")
    dialog.directionRasterBrowse.clicked.connect(lambda: select_output_file(dialog.directionRasterPath, "tif"))

    directionFileLayout = QHBoxLayout()
    directionFileLayout.addWidget(dialog.directionRasterPath)
    directionFileLayout.addWidget(dialog.directionRasterBrowse)
    finalStepLayout.addRow(directionFileLayout)
    
    # Drain Raster Output Path
    dialog.drainRasterPath = QLineEdit()
    dialog.drainRasterPath.setPlaceholderText("Choose output path for Drain Raster (r.drain)")
    dialog.drainRasterBrowse = QPushButton("Browse")
    dialog.drainRasterBrowse.clicked.connect(lambda: select_output_file(dialog.drainRasterPath, "tif"))

    drainFileLayout = QHBoxLayout()
    drainFileLayout.addWidget(dialog.drainRasterPath)
    drainFileLayout.addWidget(dialog.drainRasterBrowse)
    finalStepLayout.addRow(drainFileLayout)

    # LCP Vector Output Path (GPKG Format)
    dialog.finalPath = QLineEdit()
    dialog.finalPath.setPlaceholderText("Choose output path for LCP Vector (r.to.vect)")
    dialog.finalBrowse = QPushButton("Browse")
    dialog.finalBrowse.clicked.connect(lambda: select_output_file(dialog.finalPath, "gpkg"))

    finalFileLayout = QHBoxLayout()
    finalFileLayout.addWidget(dialog.finalPath)
    finalFileLayout.addWidget(dialog.finalBrowse)
    finalStepLayout.addRow(finalFileLayout)

    # Run Button
    dialog.final_button = QPushButton("Run r.cost, r.drain and Convert to Vector")
    finalStepLayout.addWidget(dialog.final_button)

    finalStepGroupBox.setLayout(finalStepLayout)
    middle_layout.addWidget(finalStepGroupBox)
    
    ############ STEP 7: Resample rasters ############
    
    # STEP: Raster Resampling Tool
    resampleGroupBox = QGroupBox()
    resampleGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")
    resampleLayout = QFormLayout()

    resampleTitle = QLabel("Resample Raster")
    resampleTitle.setAlignment(Qt.AlignCenter)
    resampleTitle.setStyleSheet("font-weight: bold; font-size: 12px;")
    resampleLayout.addRow(resampleTitle)
    
    infoResampleText = QLabel(
    "ⓘ For accurate GIS analysis, use a raster with a projected CRS (meters) instead of a geographic CRS (degrees), \n"
    "as degrees are not uniform in distance across different latitudes."
    )
    infoResampleText.setStyleSheet("color: lightgrey; font-size: 11px;")  # Make text bold
    resampleLayout.addRow(infoResampleText)

    # Select Input Raster
    dialog.resampleRasterComboBox = QComboBox()
    resampleLayout.addRow(QLabel("Select Raster to Resample:"), dialog.resampleRasterComboBox)
    dialog.resampleRasterComboBox.currentIndexChanged.connect(lambda: update_original_resolution(dialog))

    # Original Resolution (auto or manual)
    dialog.originalResolutionInput = QLineEdit()
    dialog.originalResolutionInput.setPlaceholderText("Original Resolution (auto or manual)")
    resampleLayout.addRow(QLabel("Original Resolution:"), dialog.originalResolutionInput)

    # Target Resolution (user input)
    dialog.targetResolutionInput = QLineEdit()
    dialog.targetResolutionInput.setPlaceholderText("Enter Target Resolution")
    resampleLayout.addRow(QLabel("Target Resolution:"), dialog.targetResolutionInput)

    # Resampling Method Dropdown
    dialog.resamplingMethodComboBox = QComboBox()
    dialog.resamplingMethodComboBox.addItems(["Nearest Neighbor", "Bilinear", "Cubic", "Lanczos"])
    resampleLayout.addRow(QLabel("Resampling Method:"), dialog.resamplingMethodComboBox)

    # Output Path Selection
    dialog.resampleOutputPath = QLineEdit()
    dialog.resampleOutputPath.setPlaceholderText("Choose output path for Resampled Raster")
    dialog.resampleBrowse = QPushButton("Browse")
    dialog.resampleBrowse.clicked.connect(lambda: select_output_file(dialog.resampleOutputPath, "tif"))

    outputFileLayout = QHBoxLayout()
    outputFileLayout.addWidget(dialog.resampleOutputPath)
    outputFileLayout.addWidget(dialog.resampleBrowse)
    resampleLayout.addRow(outputFileLayout)

    # Run Resampling Button
    dialog.runResampleButton = QPushButton("Run Resampling")
    resampleLayout.addWidget(dialog.runResampleButton)

    resampleGroupBox.setLayout(resampleLayout)
    right_layout.addWidget(resampleGroupBox)  # Add to the third column


    ############ LOG OUTPUT ############
    dialog.log_output = QTextEdit()
    dialog.log_output.setReadOnly(True)
    dialog.tabs = QTabWidget()
    dialog.tabs.addTab(dialog.log_output, "Log")
    main_layout.addWidget(dialog.tabs)

    dialog.clear_log_button = QPushButton("Clear Logs")
    main_layout.addWidget(dialog.clear_log_button)

    dialog.setLayout(main_layout)


def select_output_file(output_field: QLineEdit, file_type: str):
    """Opens a file dialog to select an output file path with the correct format."""
    if file_type == "tif":
        file_filter = "GeoTIFF (*.tif);;All Files (*)"
    elif file_type == "gpkg":
        file_filter = "GeoPackage (*.gpkg);;All Files (*)"
    else:
        file_filter = "All Files (*)"  # Fallback

    file_path, _ = QFileDialog.getSaveFileName(None, "Select Output File", "", file_filter)
    
    if file_path:
        output_field.setText(file_path)
        
def update_original_resolution(dialog):
    raster_layer = QgsProject.instance().mapLayer(dialog.resampleRasterComboBox.currentData())
    if raster_layer:
        crs = raster_layer.crs()
        resolution_x = raster_layer.rasterUnitsPerPixelX()
        resolution_y = raster_layer.rasterUnitsPerPixelY()

        # Compute the average resolution and round it
        avg_resolution = round((resolution_x + resolution_y) / 2, 2)

        # Determine unit type (meters vs. degrees)
        unit = "m" if crs.mapUnits() == QgsUnitTypes.DistanceMeters else "°"

        # Update UI with correct unit
        dialog.originalResolutionInput.setText(f"~{avg_resolution} {unit}")


