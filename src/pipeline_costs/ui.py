from typing import TYPE_CHECKING
from PyQt5.QtWidgets import (
    QVBoxLayout, QLabel, QComboBox, QLineEdit, QPushButton, QFormLayout,
    QGroupBox, QHBoxLayout, QTextEdit, QTabWidget, QCheckBox
)
from PyQt5.QtCore import Qt
from qgis.core import QgsProject, QgsUnitTypes, QgsVectorLayer

from PyQt5.QtWidgets import QLabel, QGroupBox, QVBoxLayout, QHBoxLayout

if TYPE_CHECKING:
    from ..pipeline_costs import PipelineCostsDialog

def setup_description_groupbox(dialog: 'PipelineCostsDialog'):
    descriptionGroupBox = QGroupBox()
    descriptionGroupBox.setStyleSheet("QGroupBox { border: 0px; }")
    descriptionLayout = QFormLayout()
    
    dialog.descriptionLabel = QLabel()
    dialog.descriptionLabel.setText("""
        <html>
            <body>
                <p style="text-align:justify; font-size:11px;">
                    ⓘ This submenu calculates the total pipeline cost (<b>I<sub>total</sub></b>) based on its length.
                    If the pipeline is <b>150 km or less</b>, the cost is calculated using a single <b>I<sub>P</sub></b>
                    with the total length in the <b>D</b> equation. <br> If the pipeline is longer than <b>150 km</b>, 
                    it is split into <b>segments of up to 150 km</b>, and multiple <b>I<sub>P</sub></b> values are calculated. <br>
                    In these calculations, <b>L<sub>segment</sub></b> is the length of each segment (max 150 km), while 
                    <b>L<sub>cell</sub></b> represents the pipeline length inside each GIS cell. <br>
                    Booster stations are added after every 150 km, and their costs (<b>I<sub>B</sub></b>)
                    are included in <b>I<sub>total</sub></b>.
                </p>
            </body>
        </html>
    """)
    dialog.descriptionLabel.setStyleSheet("color: lightgrey;")  # Make text bold
    descriptionLayout.addRow(dialog.descriptionLabel)
    
    descriptionGroupBox.setLayout(descriptionLayout)
    
    return descriptionGroupBox

    
def setup_formula_groupbox(dialog: 'PipelineCostsDialog'):
    """Create a group box with side-by-side equations for D and I"""
    formulaGroupBox = QGroupBox()
    formulaGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")

    formulaHLayout = QHBoxLayout()
    formulaH2Layout = QHBoxLayout()
    formulaLayout = QFormLayout()
    
    formulaTitle = QLabel("Formulas")
    formulaTitle.setAlignment(Qt.AlignCenter)
    formulaTitle.setStyleSheet("font-weight: bold; font-size: 12px;")
    formulaLayout.addRow(formulaTitle)

    # D Equation
    dialog.D_formula_label = QLabel()
    dialog.D_formula_label.setText("""
        <html>
            <body>
                <table align="center" border="0" cellspacing="0" cellpadding="5">
                    <tr>
                        <td style="font-size:25px; font-weight:bold; text-align:right;">D</td>
                        <td style="font-size:25px; font-weight:bold; text-align:center;">=</td>
                        <td style="font-size:40px; font-weight:bold; text-align:center;">(</td>
                        <td>
                            <table align="center" border="0" cellspacing="0" cellpadding="0">
                                <tr>
                                    <td style="text-align:center; font-size:18px; padding-bottom:2px;">
                                        8 ⋅ λ ⋅ M² ⋅ L<sub>segment</sub>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="border-top: 2px solid white; text-align:center; font-size:18px; padding-top:2px;">
                                        π² ⋅ &#961; ⋅ Δp
                                    </td>
                                </tr>
                            </table>
                        </td>
                        <td style="font-size:40px; font-weight:bold; text-align:center;">)</td>
                        <td style="font-size:22px; font-weight:bold; text-align:center;"><sup>1/5</sup></td>
                    </tr>
                </table>
            </body>
        </html>
    """)

    # Ip Equation
    dialog.Ip_formula_label = QLabel()
    dialog.Ip_formula_label.setText("""
        <html>
            <body>
                <p align="center" style="font-size:25px; font-weight:bold;">
                    I<sub>p</sub> = B<sub>c</sub> ⋅ D ⋅ Σ { F<sub>s</sub> ⋅ [F<sub>lu</sub> ⋅ (1 - 0.1N) + 0.1N] ⋅ L<sub>cell</sub> }
                </p>
            </body>
        </html>
    """)

    # Add both equations side by side
    formulaHLayout.addWidget(dialog.D_formula_label)
    formulaHLayout.addWidget(dialog.Ip_formula_label)
    formulaLayout.addRow(formulaHLayout)
    
    # Sc Equation
    dialog.Sc_formula_label = QLabel()
    dialog.Sc_formula_label.setText("""
        <html>
            <body>
                <table align="center" border="0" cellspacing="0" cellpadding="5">
                    <tr>
                        <td style="font-size:25px; font-weight:bold; text-align:right;">S<sub>c</sub></td>
                        <td style="font-size:25px; font-weight:bold; text-align:center;">=</td>
                        <td>
                            <table align="center" border="0" cellspacing="0" cellpadding="0">
                                <tr>
                                    <td style="text-align:center; font-size:18px; padding-bottom:2px;">
                                        M ⋅ Δp
                                    </td>
                                </tr>
                                <tr>
                                    <td style="border-top: 2px solid white; text-align:center; font-size:18px; padding-top:2px;">
                                        &#961; ⋅ B<sub>eff</sub>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </body>
        </html>
    """)
    
    # Ib Equation
    dialog.Ib_formula_label = QLabel()
    dialog.Ib_formula_label.setText("""
        <html>
            <body>
                <p align="center" style="font-size:25px; font-weight:bold;">
                    I<sub>B</sub> = 0.547 ⋅ S<sub>c</sub> + 0.42
                </p>
            </body>
        </html>
    """)
    
    formulaH2Layout.addWidget(dialog.Sc_formula_label)
    formulaH2Layout.addWidget(dialog.Ib_formula_label)
    formulaLayout.addRow(formulaH2Layout)
    
    # Itotal Equation
    dialog.Itotal_formula_label = QLabel()
    dialog.Itotal_formula_label.setText("""
        <html>
            <body>
                <p align="center" style="font-size:25px; font-weight:bold;">
                    I<sub>total</sub> = ΣI<sub>p</sub> + ΣI<sub>B</sub>
                </p>
            </body>
        </html>
    """)
    formulaLayout.addRow(dialog.Itotal_formula_label)

    formulaGroupBox.setLayout(formulaLayout)

    return formulaGroupBox


def setup_ui(dialog: 'PipelineCostsDialog'):
    """Set up the UI for PipelineCostsDialog."""
    dialog.setWindowTitle("Pipeline Price Costs")
    dialog.setGeometry(0, 0, 1050, 500)

    main_layout = QVBoxLayout()
    columns_layout = QHBoxLayout()
    left_layout = QVBoxLayout()
    right_layout = QVBoxLayout()
    
    columns_layout.addLayout(left_layout, 1)
    columns_layout.addLayout(right_layout, 1)
    
    ############ Description ############
    
    descriptionGroupBox = setup_description_groupbox(dialog)
    main_layout.addWidget(descriptionGroupBox)
    
    ############ Formula ############
    
    formula_groupbox = setup_formula_groupbox(dialog)
    main_layout.addWidget(formula_groupbox)

    main_layout.addLayout(columns_layout)

    ############ Select Cost Rasters and Vector ############
    selectionGroupBox = QGroupBox()
    selectionGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")
    selectionLayout = QFormLayout()
    
    selectionTitle = QLabel("Select Cost Rasters and Vector")
    selectionTitle.setAlignment(Qt.AlignCenter)
    selectionTitle.setStyleSheet("font-weight: bold; font-size: 12px;")
    selectionLayout.addRow(selectionTitle)

    dialog.pipelineVectorDropdown = QComboBox()
    dialog.pipelineVectorDropdown.currentIndexChanged.connect(lambda: update_pipeline_length(dialog))
    dialog.landUseCostsDropdown = QComboBox()
    dialog.landUseCostsDropdown.currentIndexChanged.connect(lambda: update_land_use_resolution(dialog))
    dialog.slopeCostsDropdown = QComboBox()
    dialog.slopeCostsDropdown.currentIndexChanged.connect(lambda: update_slope_resolution(dialog))
    selectionLayout.addRow(QLabel("Select Pipeline Vector:"), dialog.pipelineVectorDropdown)
    selectionLayout.addRow(QLabel("Select Land Use Costs Raster:"), dialog.landUseCostsDropdown)
    selectionLayout.addRow(QLabel("Select Slope Costs Raster:"), dialog.slopeCostsDropdown)
    
    dialog.landUseCostsResInput = QLineEdit()
    selectionLayout.addRow(QLabel("Land Use Costs Resolution:"), dialog.landUseCostsResInput)
    
    dialog.slopeCostsResInput = QLineEdit()
    selectionLayout.addRow(QLabel("Slope Costs Resolution:"), dialog.slopeCostsResInput)

    selectionGroupBox.setLayout(selectionLayout)
    left_layout.addWidget(selectionGroupBox)

    ############ Equation Input Variables ############
    inputGroupBox = QGroupBox()
    inputGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")
    inputLayout = QFormLayout()
    
    inputTitle = QLabel("Equation Input Variables")
    inputTitle.setAlignment(Qt.AlignCenter)
    inputTitle.setStyleSheet("font-weight: bold; font-size: 12px;")
    inputLayout.addRow(inputTitle)

    dialog.pipelineLengthInput = QLineEdit()
    dialog.pipelineLengthInput.setReadOnly(True)
    inputLayout.addRow(QLabel("Pipeline Length (L,\u00A0 in m):"), dialog.pipelineLengthInput)
    
    dialog.numInfrastructureInput = QLineEdit()
    inputLayout.addRow(QLabel("Number of infrastructure crossings (N):"), dialog.numInfrastructureInput)
    
    dialog.standardizedCostInput = QLineEdit()
    dialog.standardizedCostInput.setText("1357")
    inputLayout.addRow(QLabel("Standardized Cost Factor (B<sub>c</sub>,\u00A0 in €/m<sup>2</sup>):"), dialog.standardizedCostInput)
    
    dialog.frictionFactorInput = QLineEdit()
    dialog.frictionFactorInput.setText("0.015")
    inputLayout.addRow(QLabel("Friction Factor (λ):"), dialog.frictionFactorInput)
    
    dialog.massFlowRateInput = QLineEdit()
    inputLayout.addRow(QLabel("CO2 Mass Flow Rate (M,\u00A0 in kg/s):"), dialog.massFlowRateInput)
    
    dialog.co2densityInput = QLineEdit()
    dialog.co2densityInput.setText("827")
    inputLayout.addRow(QLabel("CO2 Density (\u03c1,\u00A0 in kg/m<sup>3</sup>):"), dialog.co2densityInput)
    
    dialog.pressureDropInput = QLineEdit()
    dialog.pressureDropInput.setText("0.02")
    inputLayout.addRow(QLabel("Admissible Pressure Drop (Δ\u0070,\u00A0 in MPa/km)"), dialog.pressureDropInput)

    inputGroupBox.setLayout(inputLayout)
    right_layout.addWidget(inputGroupBox)
    
    ############ CALCULATE BTN #########
    dialog.calculateButton = QPushButton("Calculate pipeline price")
    main_layout.addWidget(dialog.calculateButton)

    ############ LOG OUTPUT ############
    dialog.log_output = QTextEdit()
    dialog.log_output.setReadOnly(True)
    dialog.tabs = QTabWidget()
    dialog.tabs.addTab(dialog.log_output, "Log")
    main_layout.addWidget(dialog.tabs)

    dialog.clearLogButton = QPushButton("Clear Logs")
    main_layout.addWidget(dialog.clearLogButton)

    dialog.setLayout(main_layout)
    
def update_land_use_resolution(dialog):
    raster_layer = QgsProject.instance().mapLayer(dialog.landUseCostsDropdown.currentData())
    if raster_layer:
        crs = raster_layer.crs()
        resolution_x = raster_layer.rasterUnitsPerPixelX()
        resolution_y = raster_layer.rasterUnitsPerPixelY()

        # Compute the average resolution and round it
        avg_resolution = round((resolution_x + resolution_y) / 2, 2)

        # Determine unit type (meters vs. degrees)
        unit = "m" if crs.mapUnits() == QgsUnitTypes.DistanceMeters else "°"

        # Update UI with correct unit
        dialog.landUseCostsResInput.setText(f"~{avg_resolution} {unit}")
        
def update_slope_resolution(dialog):
    raster_layer = QgsProject.instance().mapLayer(dialog.slopeCostsDropdown.currentData())
    if raster_layer:
        crs = raster_layer.crs()
        resolution_x = raster_layer.rasterUnitsPerPixelX()
        resolution_y = raster_layer.rasterUnitsPerPixelY()

        # Compute the average resolution and round it
        avg_resolution = round((resolution_x + resolution_y) / 2, 2)

        # Determine unit type (meters vs. degrees)
        unit = "m" if crs.mapUnits() == QgsUnitTypes.DistanceMeters else "°"

        # Update UI with correct unit
        dialog.slopeCostsResInput.setText(f"~{avg_resolution} {unit}")

def update_pipeline_length(dialog: 'PipelineCostsDialog'):
    """Calculate the total length of the selected pipeline vector and update the input field."""
    selected_index = dialog.pipelineVectorDropdown.currentIndex()
    if selected_index == -1:
        dialog.pipelineLengthInput.setText("")
        return

    layer_id = dialog.pipelineVectorDropdown.currentData()
    layer = QgsProject.instance().mapLayer(layer_id)

    if not isinstance(layer, QgsVectorLayer):
        dialog.log_message("Selected layer is not a valid polyline vector.")
        return

    total_length = sum(f.geometry().length() for f in layer.getFeatures())
    rounded_length = str(round(total_length, 2))

    dialog.pipelineLengthInput.setText(rounded_length)
    dialog.log_message(f"Pipeline Length updated: {rounded_length} m")
