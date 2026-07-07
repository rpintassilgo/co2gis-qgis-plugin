"""Reusable builders for the output-path + Browse row and the styled GroupBox.

Both patterns were duplicated across the ``setup_*_tab`` functions; centralising
them keeps the widget wiring (placeholder text, file extension, signal hookup) and
the GroupBox styling identical everywhere.
"""

from typing import TYPE_CHECKING, Optional

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton

from ..utils import select_output_file, select_output_folder

if TYPE_CHECKING:
    from ..analysis_dialog import AnalysisDialog

# Shared border style for every framed GroupBox in the dialog.
GROUPBOX_STYLE = "QGroupBox { border: 1px solid grey; }"


def add_output_path_row(
    dialog: "AnalysisDialog",
    line_edit_attr: str,
    browse_attr: str,
    extension: str,
    placeholder: Optional[str] = None,
) -> QHBoxLayout:
    """Build an output-path row: a ``QLineEdit`` + a "Browse" button.

    The button is wired to ``select_output_file(<line_edit>, extension)``. The two
    widgets are stored on ``dialog`` under ``line_edit_attr`` / ``browse_attr`` so
    other code keeps reading them by their historical names, and the populated
    ``QHBoxLayout`` (line edit then button) is returned for the caller to place.
    """
    line_edit = QLineEdit()
    if placeholder:
        line_edit.setPlaceholderText(placeholder)
    browse = QPushButton("Browse")
    browse.clicked.connect(lambda: select_output_file(line_edit, extension))

    setattr(dialog, line_edit_attr, line_edit)
    setattr(dialog, browse_attr, browse)

    row = QHBoxLayout()
    row.addWidget(line_edit)
    row.addWidget(browse)
    return row


def add_output_folder_row(
    dialog: "AnalysisDialog",
    line_edit_attr: str,
    browse_attr: str,
    placeholder: Optional[str] = None,
) -> QHBoxLayout:
    """Build an output-folder row: a ``QLineEdit`` + a "Browse" button.

    Like :func:`add_output_path_row` but the button picks an existing directory
    (via ``select_output_folder``) — used where an action writes several files
    into a folder rather than a single file.
    """
    line_edit = QLineEdit()
    if placeholder:
        line_edit.setPlaceholderText(placeholder)
    browse = QPushButton("Browse")
    browse.clicked.connect(lambda: select_output_folder(line_edit))

    setattr(dialog, line_edit_attr, line_edit)
    setattr(dialog, browse_attr, browse)

    row = QHBoxLayout()
    row.addWidget(line_edit)
    row.addWidget(browse)
    return row


def make_group_box(title_html: str, form_layout: QFormLayout) -> QGroupBox:
    """Wrap a ``QFormLayout`` in a styled ``QGroupBox`` with a centred bold title."""
    box = QGroupBox()
    box.setStyleSheet(GROUPBOX_STYLE)
    title = QLabel(title_html)
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title.setStyleSheet("font-weight: bold; font-size: 12px;")
    form_layout.insertRow(0, title)
    box.setLayout(form_layout)
    return box
