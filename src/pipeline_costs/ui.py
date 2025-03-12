from typing import TYPE_CHECKING
from PyQt5.QtWidgets import (
    QVBoxLayout, QLabel, QComboBox, QLineEdit, QPushButton, QFormLayout,
    QGroupBox, QHBoxLayout, QTextEdit, QTabWidget, QCheckBox
)
from PyQt5.QtCore import Qt
import math

from PyQt5.QtWidgets import QLabel, QGroupBox, QVBoxLayout, QHBoxLayout

if TYPE_CHECKING:
    from ..pipeline_costs import PipelineCostsDialog

def setup_formula_groupbox(dialog: 'PipelineCostsDialog'):
    """Create a group box with side-by-side equations for D and I"""
    formulaGroupBox = QGroupBox()
    formulaGroupBox.setStyleSheet("QGroupBox { border: 1px solid grey; }")

    formulaHLayout = QHBoxLayout()
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
                                        8 ⋅ λ ⋅ M² ⋅ L
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

    # I Equation
    dialog.I_formula_label = QLabel()
    dialog.I_formula_label.setText("""
        <html>
            <body>
                <p align="center" style="font-size:25px; font-weight:bold;">
                    I = B<sub>c</sub> ⋅ D ⋅ Σ { F<sub>s</sub> ⋅ F<sub>lu</sub> ⋅ L }
                </p>
            </body>
        </html>
    """)

    # Add both equations side by side
    formulaHLayout.addWidget(dialog.D_formula_label)
    formulaHLayout.addWidget(dialog.I_formula_label)
    
    formulaLayout.addRow(formulaHLayout)

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
    dialog.landUseCostsDropdown = QComboBox()
    dialog.slopeCostsDropdown = QComboBox()
    selectionLayout.addRow(QLabel("Select Pipeline Vector:"), dialog.pipelineVectorDropdown)
    selectionLayout.addRow(QLabel("Select Land Use Costs Raster:"), dialog.landUseCostsDropdown)
    selectionLayout.addRow(QLabel("Select Slope Costs Raster:"), dialog.slopeCostsDropdown)

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

    dialog.pipelineLength = QLineEdit()
    dialog.pipelineLength.setReadOnly(True)
    inputLayout.addRow(QLabel("Pipeline Length (L,\u00A0 in m):"), dialog.pipelineLength)
    
    dialog.standardizedCostInput = QLineEdit()
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

    ############ LOG OUTPUT ############
    dialog.log_output = QTextEdit()
    dialog.log_output.setReadOnly(True)
    dialog.tabs = QTabWidget()
    dialog.tabs.addTab(dialog.log_output, "Log")
    main_layout.addWidget(dialog.tabs)

    dialog.clear_log_button = QPushButton("Clear Logs")
    main_layout.addWidget(dialog.clear_log_button)

    dialog.setLayout(main_layout)
