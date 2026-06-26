"""Dropdown UI behaviour helpers."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QComboBox, QCompleter


def make_searchable_dropdown(dropdown: QComboBox):
    """
    Makes a QComboBox searchable with autocomplete filtering.
    User can type to filter options - matches anywhere in the text.
    """
    dropdown.setEditable(True)
    dropdown.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)  # Prevent adding new items

    # Configure completer for better search experience
    completer = dropdown.completer()
    if completer:
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)  # Match anywhere in text
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)  # Case-insensitive search
