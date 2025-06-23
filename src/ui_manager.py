from typing import TYPE_CHECKING
from PyQt5.QtWidgets import (
    QVBoxLayout, QFormLayout, QTextEdit, QTabWidget, QWidget, QPushButton, QComboBox
)

from .tabs.land_use_tab import setup_land_use_tab
from .tabs.slope_tab import setup_slope_tab
from .tabs.vectors_tab import setup_vectors_tab
from .tabs.aux_tab import setup_aux_tab
from .tabs.lcp_tab import setup_lcp_tab
from .tabs.price_estimation_tab import setup_price_estimation_tab

if TYPE_CHECKING:
    from .analysis_dialog import AnalysisDialog

def setup_ui(dialog: 'AnalysisDialog'):
    """Set up the main UI for AnalysisDialog."""
    dialog.setWindowTitle("Least Cost Pipeline Analysis")
    dialog.setGeometry(0, 0, 800, 780)
    dialog.setStyleSheet("""
        QLabel, QComboBox, QPushButton, QGroupBox::title, QHeaderView::section {
            color: white;
        }
        QPushButton#populateCometButton:disabled {
            color: #808080;
        }
        QPushButton#populateCometButton {
            color: white;
        }
    """)

    main_layout = QVBoxLayout()
    
    dialog.tabs = QTabWidget()
    
    # Create tab widgets
    land_use_tab = QWidget()
    slope_tab = QWidget()
    vectors_tab = QWidget()
    aux_tab = QWidget()
    lcp_tab = QWidget()
    price_estimation_tab = QWidget()
    
    # Add tabs to the tab widget
    dialog.tabs.addTab(land_use_tab, "Land Use")
    dialog.tabs.addTab(slope_tab, "Slope")
    dialog.tabs.addTab(vectors_tab, "Corridors and Crossings")
    dialog.tabs.addTab(aux_tab, "Aux")
    dialog.tabs.addTab(lcp_tab, "LCP")
    dialog.tabs.addTab(price_estimation_tab, "Price Estimation")
    
    # Create layouts for each tab
    land_use_layout = QFormLayout()
    slope_layout = QFormLayout()
    vectors_layout = QFormLayout()
    aux_main_layout = QVBoxLayout()
    lcp_layout = QFormLayout()
    price_estimation_layout = QVBoxLayout()
    
    # Set layouts for each tab
    land_use_tab.setLayout(land_use_layout)
    slope_tab.setLayout(slope_layout)
    vectors_tab.setLayout(vectors_layout)
    aux_tab.setLayout(aux_main_layout)
    lcp_tab.setLayout(lcp_layout)
    price_estimation_tab.setLayout(price_estimation_layout)

    # Instantiate widgets that are shared or needed before tab setup
    dialog.landUseComboBox = QComboBox()

    # Setup content for each tab
    setup_land_use_tab(dialog, land_use_layout)
    setup_slope_tab(dialog, slope_layout)
    setup_vectors_tab(dialog, vectors_layout)
    setup_aux_tab(dialog, aux_main_layout)
    setup_lcp_tab(dialog, lcp_layout)
    setup_price_estimation_tab(dialog, price_estimation_layout)

    # Log output widget
    dialog.log_output = QTextEdit()
    dialog.log_output.setReadOnly(True)
    dialog.log_output.setMaximumHeight(100)
    
    dialog.clear_log_button = QPushButton("Clear Logs")

    # Add widgets to the main layout
    main_layout.addWidget(dialog.tabs)
    main_layout.addWidget(dialog.log_output)
    main_layout.addWidget(dialog.clear_log_button)

    dialog.setLayout(main_layout)
