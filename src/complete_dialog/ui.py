from typing import TYPE_CHECKING
from PyQt5.QtWidgets import (
    QVBoxLayout, QLabel, QComboBox, QTableWidget, QLineEdit, QPushButton,
    QFormLayout, QHeaderView, QTextEdit, QTabWidget, QGroupBox, QHBoxLayout
)

if TYPE_CHECKING:
    from .import Dialog
  
def setup_ui(dialog: 'Dialog'):
    dialog.setWindowTitle("Complete Analysis")
    dialog.setGeometry(0, 0, 700, 700)

    main_layout = QVBoxLayout()
    form_layout = QFormLayout()
    
    ################## POINT GROUP ##################
    # Start and End point group
    pointsGroupBox = QGroupBox()
    pointsGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")
    pointsLayout = QFormLayout()
    
    dialog.pointsComboBox = QComboBox()
    pointsLayout.addWidget(QLabel("Select Point Vector Layer Containing Start and End Points:"))
    pointsLayout.addWidget(dialog.pointsComboBox)
    
    pointsGroupBox.setLayout(pointsLayout)
    main_layout.addWidget(pointsGroupBox)
    
    ################ DEM GROUP ########################
    demGroupBox = QGroupBox()
    demGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")
    demLayout = QFormLayout()

    dialog.demComboBox = QComboBox()
    demLayout.addRow(QLabel("Select DEM Layer:"))
    demLayout.addRow(dialog.demComboBox)
    
    demGroupBox.setLayout(demLayout)
    main_layout.addWidget(demGroupBox)
    
    ################ LAND USE GROUP ########################
    # Land Use Group Box
    landUseGroupBox = QGroupBox()
    landUseGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")
    landUseLayout = QFormLayout()

    # Layer selection
    dialog.terrainComboBox = QComboBox()
    landUseLayout.addWidget(QLabel("Select Land Use Layer:"))
    landUseLayout.addWidget(dialog.terrainComboBox)

    dialog.classify_button = QPushButton("Get Classes")
    landUseLayout.addWidget(dialog.classify_button)  # Add the button directly
    
    # Class cost table
    dialog.classTable = QTableWidget()
    dialog.classTable.setColumnCount(3)
    dialog.classTable.setHorizontalHeaderLabels(["Class ID", "Class Name", "Cost"])
    dialog.classTable.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    landUseLayout.addWidget(QLabel("Land Use Classes Costs:"))
    landUseLayout.addWidget(dialog.classTable)

    landUseGroupBox.setLayout(landUseLayout)
    main_layout.addWidget(landUseGroupBox)
    
    ################ WEIGHTS GROUP ########################
    weightsGroupBox = QGroupBox()
    weightsGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")
    weightsLayout = QFormLayout()
    
    # Weights input
    dialog.demWeightInput = QLineEdit()
    dialog.demWeightInput.setPlaceholderText("Enter DEM weight")
    dialog.occupancyWeightInput = QLineEdit()
    dialog.occupancyWeightInput.setPlaceholderText("Enter occupancy weight")
    weightsLayout.addRow(QLabel("Define weights for rasters combination step:"))
    weightsLayout.addRow(QLabel("DEM Weight:"), dialog.demWeightInput)
    weightsLayout.addRow(QLabel("Occupancy Weight:"), dialog.occupancyWeightInput)
    
    weightsGroupBox.setLayout(weightsLayout)
    main_layout.addWidget(weightsGroupBox)
    
    ################## OUTPUT DIRECTORY ##################
    dialog.outputDir = QLineEdit()
    dialog.outputDir.setPlaceholderText("Choose output directory for all files")
    dialog.outputDirBrowse = QPushButton("Browse")
    dialog.outputDirBrowse.clicked.connect(dialog.select_output_directory)

    main_layout.addWidget(dialog.outputDir)
    main_layout.addWidget(dialog.outputDirBrowse)
    
    ########################################################

    # Run button and log
    dialog.run_button = QPushButton("Run Analysis")
    dialog.clear_log_button = QPushButton("Clear Logs")
    
    main_layout.addWidget(dialog.run_button)

    dialog.log_output = QTextEdit()
    dialog.log_output.setReadOnly(True)
    dialog.tabs = QTabWidget()
    dialog.tabs.addTab(dialog.log_output, "Log")
    main_layout.addWidget(dialog.tabs)
    
    main_layout.addWidget(dialog.clear_log_button)

    dialog.setLayout(main_layout)
    main_layout.addLayout(form_layout)
    