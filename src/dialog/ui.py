from typing import TYPE_CHECKING
from PyQt5.QtWidgets import (
    QVBoxLayout, QLabel, QComboBox, QTableWidget,
    QTableWidgetItem, QLineEdit, QPushButton, QHBoxLayout,
    QFormLayout, QHeaderView, QTextEdit, QTabWidget
)

if TYPE_CHECKING:
    from .import Dialog

def setup_ui(dialog: 'Dialog'):
    dialog.setWindowTitle("Least Cost Pipeline Plugin")
    dialog.setGeometry(0, 0, 600, 500)

    main_layout = QVBoxLayout()
    form_layout = QFormLayout()

    # Layer selection
    dialog.terrainComboBox = QComboBox()
    form_layout.addRow(QLabel("Terrain Occupancy Layer:"), dialog.terrainComboBox)
    dialog.classify_button = QPushButton("Classify")
    main_layout.addWidget(dialog.classify_button)

    dialog.demComboBox = QComboBox()
    form_layout.addRow(QLabel("DEM Layer:"), dialog.demComboBox)

    dialog.pointsComboBox = QComboBox()
    form_layout.addRow(QLabel("Point Vector Layer:"), dialog.pointsComboBox)
    main_layout.addLayout(form_layout)

    # Class cost table
    dialog.classTable = QTableWidget()
    dialog.classTable.setColumnCount(3)
    dialog.classTable.setHorizontalHeaderLabels(["Class ID", "Class Name", "Cost"])
    dialog.classTable.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    main_layout.addWidget(QLabel("Class Costs:"))
    main_layout.addWidget(dialog.classTable)

    # Weights input
    weights_layout = QHBoxLayout()
    dialog.demWeightInput = QLineEdit()
    dialog.demWeightInput.setPlaceholderText("Enter DEM weight")
    dialog.occupancyWeightInput = QLineEdit()
    dialog.occupancyWeightInput.setPlaceholderText("Enter occupancy weight")
    weights_layout.addWidget(QLabel("DEM Weight:"))
    weights_layout.addWidget(dialog.demWeightInput)
    weights_layout.addWidget(QLabel("Occupancy Weight:"))
    weights_layout.addWidget(dialog.occupancyWeightInput)
    main_layout.addLayout(weights_layout)

    # Run button and log
    dialog.run_button = QPushButton("Run Analysis")
    dialog.clear_log_button = QPushButton("Clear Logs")
    main_layout.addWidget(dialog.run_button)
    main_layout.addWidget(dialog.clear_log_button)

    dialog.log_output = QTextEdit()
    dialog.log_output.setReadOnly(True)
    dialog.tabs = QTabWidget()
    dialog.tabs.addTab(dialog.log_output, "Log")
    main_layout.addWidget(dialog.tabs)

    dialog.setLayout(main_layout)
