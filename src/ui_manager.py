from typing import TYPE_CHECKING

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .tabs.aux_tab import setup_aux_tab
from .tabs.corridors_tab import setup_corridors_tab
from .tabs.crossings_tab import connect_crossings_signals, setup_crossings_tab
from .tabs.land_use_tab import setup_land_use_tab
from .tabs.lcp_tab import setup_lcp_tab
from .tabs.price_estimation_tab import setup_price_estimation_tab
from .tabs.slope_tab import setup_slope_tab

if TYPE_CHECKING:
    from .analysis_dialog import AnalysisDialog


def setup_ui(dialog: "AnalysisDialog"):
    """Set up the main UI for AnalysisDialog."""
    dialog.setWindowTitle("CO2GIS")
    dialog.setMinimumSize(900, 600)
    dialog.resize(1200, 820)
    dialog.setSizeGripEnabled(True)
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
        QSplitter::handle {
            background-color: #555555;
            height: 4px;
        }
        QSplitter::handle:hover {
            background-color: #888888;
        }
    """)

    main_layout = QVBoxLayout()

    dialog.tabs = QTabWidget()

    # Create tab widgets
    land_use_tab = QWidget()
    slope_tab = QWidget()
    crossings_tab = QWidget()
    corridors_tab = QWidget()
    aux_tab = QWidget()
    lcp_tab = QWidget()
    price_estimation_tab = QWidget()

    # Add tabs to the tab widget
    dialog.tabs.addTab(land_use_tab, "Land Use")
    dialog.tabs.addTab(slope_tab, "Slope")
    dialog.tabs.addTab(crossings_tab, "Crossings")
    dialog.tabs.addTab(corridors_tab, "Corridors")
    dialog.tabs.addTab(aux_tab, "Aux")
    dialog.tabs.addTab(lcp_tab, "LCP")
    dialog.tabs.addTab(price_estimation_tab, "Price Estimation")

    # Create layouts for each tab
    land_use_layout = QFormLayout()
    slope_layout = QFormLayout()
    crossings_layout = QFormLayout()
    corridors_layout = QFormLayout()
    aux_main_layout = QVBoxLayout()
    lcp_layout = QFormLayout()
    price_estimation_layout = QVBoxLayout()

    # Set layouts for each tab
    land_use_tab.setLayout(land_use_layout)
    slope_tab.setLayout(slope_layout)
    crossings_tab.setLayout(crossings_layout)
    corridors_tab.setLayout(corridors_layout)
    aux_tab.setLayout(aux_main_layout)
    lcp_tab.setLayout(lcp_layout)
    price_estimation_tab.setLayout(price_estimation_layout)

    # Instantiate widgets that are shared or needed before tab setup
    dialog.landUseComboBox = QComboBox()

    # Setup content for each tab
    setup_land_use_tab(dialog, land_use_layout)
    setup_slope_tab(dialog, slope_layout)
    setup_crossings_tab(dialog, crossings_layout)
    setup_corridors_tab(dialog, corridors_layout)
    setup_aux_tab(dialog, aux_main_layout)
    setup_lcp_tab(dialog, lcp_layout)
    setup_price_estimation_tab(dialog, price_estimation_layout)

    # Connect signals
    connect_crossings_signals(dialog)

    # --- Log panel ---
    dialog.log_output = QTextEdit()
    dialog.log_output.setReadOnly(True)

    # Bottom bar: Clear Logs + Pop Out button
    log_buttons_layout = QHBoxLayout()
    dialog.clear_log_button = QPushButton("Clear Logs")
    dialog.popout_log_button = QPushButton("⧉ Pop Out Log")
    dialog.popout_log_button.setToolTip("Open the log in a separate floating window")
    log_buttons_layout.addWidget(dialog.clear_log_button)
    log_buttons_layout.addWidget(dialog.popout_log_button)

    log_buttons_widget = QWidget()
    log_buttons_widget.setLayout(log_buttons_layout)

    # Log container (log text + buttons), used inside the splitter
    log_container = QWidget()
    log_container_layout = QVBoxLayout(log_container)
    log_container_layout.setContentsMargins(0, 0, 0, 0)
    log_container_layout.setSpacing(2)
    log_container_layout.addWidget(dialog.log_output)
    log_container_layout.addWidget(log_buttons_widget)

    # Splitter: tabs on top, log panel on bottom — user can drag to resize
    dialog.main_splitter = QSplitter(Qt.Orientation.Vertical)
    dialog.main_splitter.addWidget(dialog.tabs)
    dialog.main_splitter.addWidget(log_container)
    dialog.main_splitter.setStretchFactor(0, 4)
    dialog.main_splitter.setStretchFactor(1, 1)
    dialog.main_splitter.setSizes([640, 160])
    dialog.main_splitter.setCollapsible(0, False)
    dialog.main_splitter.setCollapsible(1, True)

    main_layout.addWidget(dialog.main_splitter)
    dialog.setLayout(main_layout)

    # Pop-out log window (created lazily)
    dialog._log_popout_window = None

    def _toggle_popout():
        if dialog._log_popout_window is None or not dialog._log_popout_window.isVisible():
            # Create floating log window
            win = QDialog(None)  # no parent so it's truly independent
            win.setWindowTitle("Log Output")
            win.setMinimumSize(600, 300)
            win.resize(800, 400)
            win.setSizeGripEnabled(True)
            win.setStyleSheet(
                "QDialog { background-color: #2a2a2a; } QTextEdit { color: white; background-color: #1e1e1e; }"
            )
            win_layout = QVBoxLayout(win)
            win_layout.setContentsMargins(6, 6, 6, 6)

            # Mirror: share the same QTextEdit document so both views stay in sync
            popout_view = QTextEdit()
            popout_view.setReadOnly(True)
            popout_view.setDocument(dialog.log_output.document())
            win_layout.addWidget(popout_view)

            # Hide the inline log, give all space to the tabs
            dialog.log_output.hide()
            dialog.main_splitter.setSizes([dialog.main_splitter.height() - 30, 30])
            dialog.popout_log_button.setText("⧉ Close Log Window")

            def _on_close():
                dialog.log_output.show()
                dialog.main_splitter.setSizes([640, 160])
                dialog.popout_log_button.setText("⧉ Pop Out Log")

            win.finished.connect(_on_close)
            dialog._log_popout_window = win
            win.show()
        else:
            dialog._log_popout_window.close()

    dialog.popout_log_button.clicked.connect(_toggle_popout)
