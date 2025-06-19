from typing import TYPE_CHECKING
from PyQt5.QtWidgets import (
    QVBoxLayout, QLabel, QComboBox, QTableWidget, QLineEdit, QPushButton, QCheckBox,
    QFormLayout, QHeaderView, QTextEdit, QTabWidget, QGroupBox, QHBoxLayout, QFileDialog,
    QWidget
)
from PyQt5.QtCore import Qt
from qgis.core import QgsProject, QgsUnitTypes

if TYPE_CHECKING:
    from . import StepByStepDialog

def setup_ui(dialog: 'StepByStepDialog'):
    """Set up the UI for StepByStepDialog."""
    dialog.setWindowTitle("Step-by-Step Analysis")
    dialog.setGeometry(0, 0, 800, 800)  # Adjusted size for tabbed layout

    main_layout = QVBoxLayout()
    
    # Create tab widget
    dialog.tabs = QTabWidget()
    
    # Create the five tabs
    land_use_tab = QWidget()
    slope_tab = QWidget()
    vectors_tab = QWidget()
    aux_tab = QWidget()
    lcp_tab = QWidget()
    
    # Add tabs to tab widget
    dialog.tabs.addTab(land_use_tab, "Land Use")
    dialog.tabs.addTab(slope_tab, "Slope")
    dialog.tabs.addTab(vectors_tab, "Corridors and Crossings")
    dialog.tabs.addTab(aux_tab, "Aux")
    dialog.tabs.addTab(lcp_tab, "LCP")
    
    # Setup layouts for each tab
    land_use_layout = QFormLayout()
    slope_layout = QFormLayout()
    vectors_layout = QFormLayout()
    aux_main_layout = QVBoxLayout()
    lcp_layout = QFormLayout()
    
    land_use_tab.setLayout(land_use_layout)
    slope_tab.setLayout(slope_layout)
    vectors_tab.setLayout(vectors_layout)
    aux_tab.setLayout(aux_main_layout)
    lcp_tab.setLayout(lcp_layout)

    ############ Land Use Tab ############
    dialog.terrainComboBox = QComboBox()
    land_use_layout.addRow(QLabel("Select Land Use Layer:"), dialog.terrainComboBox)

    # Land Use Classes Table
    dialog.classTable = QTableWidget()
    dialog.classTable.setColumnCount(3)
    dialog.classTable.setHorizontalHeaderLabels(["Class ID", "Class Name", "Cost"])
    dialog.classTable.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    land_use_layout.addRow(QLabel("Land Use Classes Costs:"))
    land_use_layout.addRow(dialog.classTable)
    
    # File path selection for land use costs
    dialog.costsRasterPath = QLineEdit()
    dialog.costsRasterPath.setPlaceholderText("Choose output path for Costs Raster")
    dialog.costsRasterBrowse = QPushButton("Browse")
    dialog.costsRasterBrowse.clicked.connect(lambda: select_output_file(dialog.costsRasterPath, "tif"))
    
    costsfileLayout = QHBoxLayout()
    costsfileLayout.addWidget(dialog.costsRasterPath)
    costsfileLayout.addWidget(dialog.costsRasterBrowse)
    land_use_layout.addRow(costsfileLayout)

    dialog.create_land_use_costs_button = QPushButton("Create Land Use Costs Raster")
    land_use_layout.addRow(dialog.create_land_use_costs_button)

    ############ Slope Tab ############
    # First Group Box - Create Slope from DEM
    createSlopeGroupBox = QGroupBox()
    createSlopeGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")
    createSlopeLayout = QFormLayout()
    
    # Title for Create Slope
    createSlopeTitle = QLabel("Create Slope from DEM")
    createSlopeTitle.setAlignment(Qt.AlignCenter)
    createSlopeTitle.setStyleSheet("font-weight: bold; font-size: 12px;")
    createSlopeLayout.addRow(createSlopeTitle)
    
    dialog.demComboBox = QComboBox()
    createSlopeLayout.addRow(QLabel("Select DEM Layer:"), dialog.demComboBox)
    
    # Slope raster output path
    dialog.slopeRasterPath = QLineEdit()
    dialog.slopeRasterPath.setPlaceholderText("Choose output path for Slope Raster")
    dialog.slopeRasterBrowse = QPushButton("Browse")
    dialog.slopeRasterBrowse.clicked.connect(lambda: select_output_file(dialog.slopeRasterPath, "tif"))
    
    slopeFileLayout = QHBoxLayout()
    slopeFileLayout.addWidget(dialog.slopeRasterPath)
    slopeFileLayout.addWidget(dialog.slopeRasterBrowse)
    createSlopeLayout.addRow(slopeFileLayout)

    dialog.create_slope_button = QPushButton("Create Slope Raster from DEM")
    createSlopeLayout.addRow(dialog.create_slope_button)
    
    createSlopeGroupBox.setLayout(createSlopeLayout)
    slope_layout.addWidget(createSlopeGroupBox)

    # Second Group Box - Create Slope Costs
    slopeCostsGroupBox = QGroupBox()
    slopeCostsGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")
    slopeCostsLayout = QFormLayout()
    
    # Title for Create Slope Costs
    slopeCostsTitle = QLabel("Create Slope Costs")
    slopeCostsTitle.setAlignment(Qt.AlignCenter)
    slopeCostsTitle.setStyleSheet("font-weight: bold; font-size: 12px;")
    slopeCostsLayout.addRow(slopeCostsTitle)

    # Select Slope Layer Dropdown
    dialog.slopeLayerComboBox = QComboBox()
    slopeCostsLayout.addRow(QLabel("Select Slope Layer:"), dialog.slopeLayerComboBox)

    # Slope Cost Intervals Label (left-aligned)
    slopeCostsLayout.addRow(QLabel("Define Slope Cost Intervals:"))

    # Slope Cost Table
    dialog.slopeCostTable = QTableWidget()
    dialog.slopeCostTable.setColumnCount(4)
    dialog.slopeCostTable.setHorizontalHeaderLabels(["Min % Slope", "Max % Slope", "Cost", "No Upper Limit"])
    dialog.slopeCostTable.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    slopeCostsLayout.addRow(dialog.slopeCostTable)

    # Add/Remove Row Buttons for slope table
    slopeTableButtonsLayout = QHBoxLayout()
    dialog.addSlopeRowButton = QPushButton("Add Row")
    dialog.removeSlopeRowButton = QPushButton("Remove Selected Row")
    slopeTableButtonsLayout.addWidget(dialog.addSlopeRowButton)
    slopeTableButtonsLayout.addWidget(dialog.removeSlopeRowButton)
    slopeCostsLayout.addRow(slopeTableButtonsLayout)

    # Slope costs raster output path
    dialog.slopeCostsRasterPath = QLineEdit()
    dialog.slopeCostsRasterPath.setPlaceholderText("Choose output path for Slope Costs Raster")
    dialog.slopeCostsRasterBrowse = QPushButton("Browse")
    dialog.slopeCostsRasterBrowse.clicked.connect(lambda: select_output_file(dialog.slopeCostsRasterPath, "tif"))
    
    slopeCostsFileLayout = QHBoxLayout()
    slopeCostsFileLayout.addWidget(dialog.slopeCostsRasterPath)
    slopeCostsFileLayout.addWidget(dialog.slopeCostsRasterBrowse)
    slopeCostsLayout.addRow(slopeCostsFileLayout)

    dialog.create_slope_costs_button = QPushButton("Create Slope Costs Raster")
    slopeCostsLayout.addRow(dialog.create_slope_costs_button)

    slopeCostsGroupBox.setLayout(slopeCostsLayout)
    slope_layout.addWidget(slopeCostsGroupBox)

    ############ Vectors Tab ############
    # Select vector to create raster
    dialog.vectorRasterComboBox = QComboBox()
    vectors_layout.addRow(QLabel("Select Vector:"), dialog.vectorRasterComboBox)
    
    # Select reference raster
    dialog.refRasterComboBox = QComboBox()
    vectors_layout.addRow(QLabel("Select Reference Raster:"), dialog.refRasterComboBox)
    
    # Cost inputs
    dialog.hasVectorCostInput = QLineEdit()
    dialog.hasVectorCostInput.setPlaceholderText("Enter cost where vector is present")
    dialog.hasNotVectorCostInput = QLineEdit()
    dialog.hasNotVectorCostInput.setPlaceholderText("Enter cost where vector is absent")
    vectors_layout.addRow(QLabel("Cost for vector-covered cells:"), dialog.hasVectorCostInput)
    vectors_layout.addRow(QLabel("Cost for non-vector cells:"), dialog.hasNotVectorCostInput)
    
    # Output Path Selection
    dialog.vectorRasterOutputPath = QLineEdit()
    dialog.vectorRasterOutputPath.setPlaceholderText("Choose output path for Raster")
    dialog.vectorRasterBrowse = QPushButton("Browse")
    dialog.vectorRasterBrowse.clicked.connect(lambda: select_output_file(dialog.vectorRasterOutputPath, "tif"))
    
    outputVectorRasterLayout = QHBoxLayout()
    outputVectorRasterLayout.addWidget(dialog.vectorRasterOutputPath)
    outputVectorRasterLayout.addWidget(dialog.vectorRasterBrowse)
    vectors_layout.addRow(outputVectorRasterLayout)
    
    # Create button
    dialog.runCreateRasterFromVectorButton = QPushButton("Create cost raster from vector")
    vectors_layout.addRow(dialog.runCreateRasterFromVectorButton)

    ############ Aux Tab ############
    # First Group Box - Combine Vectors
    combineVectorsGroupBox = QGroupBox()
    combineVectorsGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")
    combineVectorsLayout = QFormLayout()
    
    # Title for Combine Vectors
    combineVectorsTitle = QLabel("Combine Vectors")
    combineVectorsTitle.setAlignment(Qt.AlignCenter)
    combineVectorsTitle.setStyleSheet("font-weight: bold; font-size: 12px;")
    combineVectorsLayout.addRow(combineVectorsTitle)
    
    # Helper text for Combine Vectors
    infoCombineText = QLabel(
        "ⓘ Combine vectors functionality is useful to combine roads and railroads vectors for crossings to calculate crossings cost raster in Corridors and Crossings tab later."
    )
    infoCombineText.setStyleSheet("color: lightgrey; font-size: 11px;")
    infoCombineText.setWordWrap(True)
    combineVectorsLayout.addRow(infoCombineText)
    
    # Select Input Vectors
    dialog.vectorComboBox = QComboBox()
    dialog.vector2ComboBox = QComboBox()
    vectorSelectionLayout = QHBoxLayout()
    vectorSelectionLayout.addWidget(dialog.vectorComboBox)
    vectorSelectionLayout.addWidget(dialog.vector2ComboBox)
    combineVectorsLayout.addRow(QLabel("Select Vectors:"), vectorSelectionLayout)

    # Output Path Selection for combined vectors
    dialog.vectorsOutputPath = QLineEdit()
    dialog.vectorsOutputPath.setPlaceholderText("Choose output path for Combined Vectors")
    dialog.vectorsBrowse = QPushButton("Browse")
    dialog.vectorsBrowse.clicked.connect(lambda: select_output_file(dialog.vectorsOutputPath, "ogr"))
    
    outputVectorsLayout = QHBoxLayout()
    outputVectorsLayout.addWidget(dialog.vectorsOutputPath)
    outputVectorsLayout.addWidget(dialog.vectorsBrowse)
    combineVectorsLayout.addRow(outputVectorsLayout)

    # Run Combine Vectors Button
    dialog.runCombineVectorsButton = QPushButton("Combine vectors")
    combineVectorsLayout.addRow(dialog.runCombineVectorsButton)
    
    combineVectorsGroupBox.setLayout(combineVectorsLayout)
    aux_main_layout.addWidget(combineVectorsGroupBox)

    # Second Group Box - Resample Raster
    resampleGroupBox = QGroupBox()
    resampleGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")
    resampleLayout = QFormLayout()
    
    # Title for Resample
    resampleTitle = QLabel("Resample Raster")
    resampleTitle.setAlignment(Qt.AlignCenter)
    resampleTitle.setStyleSheet("font-weight: bold; font-size: 12px;")
    resampleLayout.addRow(resampleTitle)
    
    # Helper text for Resample
    infoResampleText = QLabel(
        "ⓘ For accurate GIS analysis, use a raster with a projected CRS (meters) instead of a geographic CRS (degrees), as degrees are not uniform in distance across different latitudes."
    )
    infoResampleText.setStyleSheet("color: lightgrey; font-size: 11px;")
    infoResampleText.setWordWrap(True)
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

    resampleOutputLayout = QHBoxLayout()
    resampleOutputLayout.addWidget(dialog.resampleOutputPath)
    resampleOutputLayout.addWidget(dialog.resampleBrowse)
    resampleLayout.addRow(resampleOutputLayout)

    # Run Resampling Button
    dialog.runResampleButton = QPushButton("Run Resampling")
    resampleLayout.addRow(dialog.runResampleButton)

    resampleGroupBox.setLayout(resampleLayout)
    aux_main_layout.addWidget(resampleGroupBox)

    # Third Group Box - Clip Raster
    clipGroupBox = QGroupBox()
    clipGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")
    clipLayout = QFormLayout()
    
    # Title for Clip
    clipTitle = QLabel("Clip Raster to Area")
    clipTitle.setAlignment(Qt.AlignCenter)
    clipTitle.setStyleSheet("font-weight: bold; font-size: 12px;")
    clipLayout.addRow(clipTitle)

    # Helper text for Clip Raster
    infoClipText = QLabel(
        "ⓘ This functionality clips rasters based on a two-point vector layer (like a rectangle between points). It's useful to reduce raster sizes for faster processing. For example, when calculating a new LCP, you can clip DEM and land use rasters to make computations lighter. While unlikely, some edge cases might lose precision since routes outside the clipped area are not considered. For instance, in scenarios with water bodies, a cheaper route might exist that goes around the clipped area."
    )
    infoClipText.setStyleSheet("color: lightgrey; font-size: 11px;")
    infoClipText.setWordWrap(True)
    clipLayout.addRow(infoClipText)

    # Point vector selection for clipping
    dialog.clipPointVectorComboBox = QComboBox()
    clipLayout.addRow(QLabel("Select Point Vector Layer:"), dialog.clipPointVectorComboBox)

    dialog.step4Dropdown = QComboBox()
    clipLayout.addRow(QLabel("Select Raster To Clip:"), dialog.step4Dropdown)
    
    dialog.copySymbologyCheckbox = QCheckBox("Copy Symbology to Clipped Raster")
    dialog.copySymbologyCheckbox.setChecked(False)
    clipLayout.addRow(dialog.copySymbologyCheckbox)
    
    dialog.clippedRasterPath = QLineEdit()
    dialog.clippedRasterPath.setPlaceholderText("Choose output path for Clipped Raster")
    dialog.clippedRasterBrowse = QPushButton("Browse")
    dialog.clippedRasterBrowse.clicked.connect(lambda: select_output_file(dialog.clippedRasterPath, "tif"))
    
    clippedFileLayout = QHBoxLayout()
    clippedFileLayout.addWidget(dialog.clippedRasterPath)
    clippedFileLayout.addWidget(dialog.clippedRasterBrowse)
    clipLayout.addRow(clippedFileLayout)

    dialog.clip_button = QPushButton("Clip Raster to Area")
    clipLayout.addRow(dialog.clip_button)

    clipGroupBox.setLayout(clipLayout)
    aux_main_layout.addWidget(clipGroupBox)

    ############ LCP Tab ############
    # First Group Box - Create Combined Costs Raster
    combinedCostsGroupBox = QGroupBox()
    combinedCostsGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")
    combinedCostsLayout = QFormLayout()
    
    # Title for Combined Costs
    combinedCostsTitle = QLabel("Create Combined Costs Raster")
    combinedCostsTitle.setAlignment(Qt.AlignCenter)
    combinedCostsTitle.setStyleSheet("font-weight: bold; font-size: 12px;")
    combinedCostsLayout.addRow(combinedCostsTitle)

    dialog.step3LandUseDropdown = QComboBox()
    dialog.step3SlopeDropdown = QComboBox()
    dialog.step3CorridorsDropdown = QComboBox()
    dialog.step3CrossingsDropdown = QComboBox()
    
    combinedCostsLayout.addRow(QLabel("Select Land Use Costs Raster:"), dialog.step3LandUseDropdown)
    combinedCostsLayout.addRow(QLabel("Select Slope Costs Raster:"), dialog.step3SlopeDropdown)
    combinedCostsLayout.addRow(QLabel("Select Corridors Costs Raster:"), dialog.step3CorridorsDropdown)
    combinedCostsLayout.addRow(QLabel("Select Crossings Costs Raster:"), dialog.step3CrossingsDropdown)

    # Weights
    dialog.landUseCostWeightInput = QLineEdit()
    dialog.slopeRasterWeightInput = QLineEdit()
    dialog.corridorsRasterWeightInput = QLineEdit()
    dialog.crossingsRasterWeightInput = QLineEdit()

    combinedCostsLayout.addRow(QLabel("Land Use Costs Weight:"), dialog.landUseCostWeightInput)
    combinedCostsLayout.addRow(QLabel("Slope Costs Weight:"), dialog.slopeRasterWeightInput)
    combinedCostsLayout.addRow(QLabel("Corridors Costs Weight:"), dialog.corridorsRasterWeightInput)
    combinedCostsLayout.addRow(QLabel("Crossings Costs Weight:"), dialog.crossingsRasterWeightInput)
    
    # Combined raster output path
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
    lcp_layout.addWidget(combinedCostsGroupBox)

    # Second Group Box - Create Least Cost Path
    lcpGroupBox = QGroupBox()
    lcpGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")
    lcpPathLayout = QFormLayout()
    
    # Title for LCP
    lcpTitle = QLabel("Create Least Cost Path")
    lcpTitle.setAlignment(Qt.AlignCenter)
    lcpTitle.setStyleSheet("font-weight: bold; font-size: 12px;")
    lcpPathLayout.addRow(lcpTitle)

    dialog.pointsComboBox = QComboBox()
    lcpPathLayout.addRow(QLabel("Select Point Vector Layer:"), dialog.pointsComboBox)

    dialog.step5Dropdown = QComboBox()
    lcpPathLayout.addRow(QLabel("Select Combined Raster:"), dialog.step5Dropdown)

    # Cost Raster Output Path
    dialog.costRasterPath = QLineEdit()
    dialog.costRasterPath.setPlaceholderText("Choose output path for Cost Raster (r.cost)")
    dialog.costRasterBrowse = QPushButton("Browse")
    dialog.costRasterBrowse.clicked.connect(lambda: select_output_file(dialog.costRasterPath, "tif"))

    costFileLayout = QHBoxLayout()
    costFileLayout.addWidget(dialog.costRasterPath)
    costFileLayout.addWidget(dialog.costRasterBrowse)
    lcpPathLayout.addRow(costFileLayout)

    # Direction Raster Output Path
    dialog.directionRasterPath = QLineEdit()
    dialog.directionRasterPath.setPlaceholderText("Choose output path for Direction Raster (r.cost)")
    dialog.directionRasterBrowse = QPushButton("Browse")
    dialog.directionRasterBrowse.clicked.connect(lambda: select_output_file(dialog.directionRasterPath, "tif"))

    directionFileLayout = QHBoxLayout()
    directionFileLayout.addWidget(dialog.directionRasterPath)
    directionFileLayout.addWidget(dialog.directionRasterBrowse)
    lcpPathLayout.addRow(directionFileLayout)
    
    # Drain Raster Output Path
    dialog.drainRasterPath = QLineEdit()
    dialog.drainRasterPath.setPlaceholderText("Choose output path for Drain Raster (r.drain)")
    dialog.drainRasterBrowse = QPushButton("Browse")
    dialog.drainRasterBrowse.clicked.connect(lambda: select_output_file(dialog.drainRasterPath, "tif"))

    drainFileLayout = QHBoxLayout()
    drainFileLayout.addWidget(dialog.drainRasterPath)
    drainFileLayout.addWidget(dialog.drainRasterBrowse)
    lcpPathLayout.addRow(drainFileLayout)

    # LCP Vector Output Path (GPKG Format)
    dialog.finalPath = QLineEdit()
    dialog.finalPath.setPlaceholderText("Choose output path for LCP Vector (r.to.vect)")
    dialog.finalBrowse = QPushButton("Browse")
    dialog.finalBrowse.clicked.connect(lambda: select_output_file(dialog.finalPath, "gpkg"))

    finalFileLayout = QHBoxLayout()
    finalFileLayout.addWidget(dialog.finalPath)
    finalFileLayout.addWidget(dialog.finalBrowse)
    lcpPathLayout.addRow(finalFileLayout)

    # Run Button
    dialog.final_button = QPushButton("Run r.cost, r.drain and Convert to Vector")
    lcpPathLayout.addRow(dialog.final_button)

    lcpGroupBox.setLayout(lcpPathLayout)
    lcp_layout.addWidget(lcpGroupBox)

    # Add log output area at the bottom of the main window
    dialog.log_output = QTextEdit()
    dialog.log_output.setReadOnly(True)
    dialog.log_output.setMaximumHeight(100)
    main_layout.addWidget(dialog.tabs)
    main_layout.addWidget(dialog.log_output)

    # Add clear log button
    dialog.clear_log_button = QPushButton("Clear Logs")
    main_layout.addWidget(dialog.clear_log_button)

    dialog.setLayout(main_layout)

def select_output_file(output_field: QLineEdit, file_type: str):
    """Open a file dialog to select an output file location."""
    file_dialog = QFileDialog()
    file_dialog.setFileMode(QFileDialog.AnyFile)
    file_dialog.setAcceptMode(QFileDialog.AcceptSave)
    file_dialog.setNameFilter(f"*.{file_type}")
    
    if file_dialog.exec_():
        selected_files = file_dialog.selectedFiles()
        if selected_files:
            selected_file = selected_files[0]
            if not selected_file.endswith(f".{file_type}"):
                selected_file += f".{file_type}"
            output_field.setText(selected_file)

def update_original_resolution(dialog):
    """Update the original resolution input field based on the selected raster."""
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


