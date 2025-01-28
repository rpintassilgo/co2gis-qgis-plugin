from typing import TYPE_CHECKING
from PyQt5.QtWidgets import (
    QVBoxLayout, QLabel, QComboBox, QTableWidget, QLineEdit, QPushButton,
    QFormLayout, QHeaderView, QTextEdit, QTabWidget, QGroupBox, QHBoxLayout, QFileDialog
)
from PyQt5.QtCore import Qt

if TYPE_CHECKING:
    from . import StepByStepDialog

def setup_ui(dialog: 'StepByStepDialog'):
    """Set up the UI for StepByStepDialog."""
    dialog.setWindowTitle("Step-by-Step Analysis")
    dialog.setGeometry(0, 0, 700, 900)

    main_layout = QVBoxLayout()

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
    main_layout.addWidget(pointsGroupBox)

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
    dialog.slopeRasterBrowse.clicked.connect(lambda: select_output_file(dialog.slopeRasterPath))
    
    fileLayout = QHBoxLayout()
    fileLayout.addWidget(dialog.slopeRasterPath)
    fileLayout.addWidget(dialog.slopeRasterBrowse)
    demLayout.addRow(fileLayout)

    dialog.create_slope_button = QPushButton("Create Slope Raster from DEM")
    demLayout.addWidget(dialog.create_slope_button)

    demGroupBox.setLayout(demLayout)
    main_layout.addWidget(demGroupBox)

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
    dialog.costsRasterBrowse.clicked.connect(lambda: select_output_file(dialog.costsRasterPath))
    
    costsfileLayout = QHBoxLayout()
    costsfileLayout.addWidget(dialog.costsRasterPath)
    costsfileLayout.addWidget(dialog.costsRasterBrowse)
    landUseLayout.addRow(costsfileLayout)

    dialog.create_land_use_costs_button = QPushButton("Create Land Use Costs Raster")
    landUseLayout.addWidget(dialog.create_land_use_costs_button)

    landUseGroupBox.setLayout(landUseLayout)
    main_layout.addWidget(landUseGroupBox)

    ############ STEP 4: Combine Rasters (Land Use & Slope) ############
    combineGroupBox = QGroupBox()
    combineGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")
    combineLayout = QFormLayout()
    
    combineTitle = QLabel("Combine Rasters (Land Use and Slope)")
    combineTitle.setAlignment(Qt.AlignCenter)  # Center the label text
    combineTitle.setStyleSheet("font-weight: bold; font-size: 12px;")  # Make text bold
    combineLayout.addRow(combineTitle)

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
    dialog.combinedRasterBrowse.clicked.connect(lambda: select_output_file(dialog.combinedRasterPath))
    
    combinedfileLayout = QHBoxLayout()
    combinedfileLayout.addWidget(dialog.combinedRasterPath)
    combinedfileLayout.addWidget(dialog.combinedRasterBrowse)
    combineLayout.addRow(combinedfileLayout)

    dialog.combine_button = QPushButton("Combine Rasters")
    combineLayout.addRow(dialog.combine_button)

    combineGroupBox.setLayout(combineLayout)
    main_layout.addWidget(combineGroupBox)

    ############ STEP 5: Select Combined Raster & Clip ############
    clipGroupBox = QGroupBox()
    clipGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")
    clipLayout = QFormLayout()
    
    clipTitle = QLabel("Select Combined Raster and Create Clipped Raster")
    clipTitle.setAlignment(Qt.AlignCenter)  # Center the label text
    clipTitle.setStyleSheet("font-weight: bold; font-size: 12px;")  # Make text bold
    clipLayout.addRow(clipTitle)

    dialog.step4Dropdown = QComboBox()
    clipLayout.addRow(QLabel("Select Combined Raster:"))
    clipLayout.addRow(dialog.step4Dropdown)
    
    # File path selection
    dialog.clippedRasterPath = QLineEdit()
    dialog.clippedRasterPath.setPlaceholderText("Choose output path for Clipped Raster")
    dialog.clippedRasterBrowse = QPushButton("Browse")
    dialog.clippedRasterBrowse.clicked.connect(lambda: select_output_file(dialog.clippedRasterPath))
    
    combinedfileLayout = QHBoxLayout()
    combinedfileLayout.addWidget(dialog.clippedRasterPath)
    combinedfileLayout.addWidget(dialog.clippedRasterBrowse)
    clipLayout.addRow(combinedfileLayout)

    dialog.clip_button = QPushButton("Clip Combined Raster to Area")
    clipLayout.addWidget(dialog.clip_button)

    clipGroupBox.setLayout(clipLayout)
    main_layout.addWidget(clipGroupBox)

    ############ STEP 6: Select Clipped Combined Raster & Run r.cost, r.drain ############
    finalStepGroupBox = QGroupBox()
    finalStepGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")
    finalStepLayout = QFormLayout()
    
    finalTitle = QLabel("Create Least Cost Path Vector from Entire or Clipped Raster")
    finalTitle.setAlignment(Qt.AlignCenter)  # Center the label text
    finalTitle.setStyleSheet("font-weight: bold; font-size: 12px;")  # Make text bold
    finalStepLayout.addRow(finalTitle)

    dialog.step5Dropdown = QComboBox()
    finalStepLayout.addRow(QLabel("Select Clipped Combined Raster:"))
    finalStepLayout.addRow(dialog.step5Dropdown)
    
    # File path selection
    dialog.finalPath = QLineEdit()
    dialog.finalPath.setPlaceholderText("Choose output path for LCP Vector")
    dialog.finalBrowse = QPushButton("Browse")
    dialog.finalBrowse.clicked.connect(lambda: select_output_file(dialog.finalPath))
    
    finalfileLayout = QHBoxLayout()
    finalfileLayout.addWidget(dialog.finalPath)
    finalfileLayout.addWidget(dialog.finalBrowse)
    finalStepLayout.addRow(finalfileLayout)

    dialog.final_button = QPushButton("Run r.cost, r.drain and Convert to Vector")
    finalStepLayout.addWidget(dialog.final_button)

    finalStepGroupBox.setLayout(finalStepLayout)
    main_layout.addWidget(finalStepGroupBox)

    ############ LOG OUTPUT ############
    dialog.log_output = QTextEdit()
    dialog.log_output.setReadOnly(True)
    dialog.tabs = QTabWidget()
    dialog.tabs.addTab(dialog.log_output, "Log")
    main_layout.addWidget(dialog.tabs)

    dialog.clear_log_button = QPushButton("Clear Logs")
    main_layout.addWidget(dialog.clear_log_button)

    dialog.setLayout(main_layout)

def select_output_file(output_field: QLineEdit):
    """Opens a file dialog to select an output file path."""
    file_path, _ = QFileDialog.getSaveFileName(None, "Select Output File", "", "GeoTIFF (*.tif);;All Files (*)")
    if file_path:
        output_field.setText(file_path)