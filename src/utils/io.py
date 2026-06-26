"""File-dialog helpers."""

import os

from qgis.PyQt.QtWidgets import QFileDialog, QLineEdit


def select_output_file(output_field: QLineEdit, file_type: str):
    """Open a file dialog to select an output file location."""
    file_dialog = QFileDialog()
    file_dialog.setFileMode(QFileDialog.FileMode.AnyFile)
    file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)

    if file_type == "tif":
        name_filter = "TIF files (*.tif)"
    elif file_type == "gpkg":
        name_filter = "GeoPackage files (*.gpkg)"
    elif file_type == "ogr":
        name_filter = "ESRI Shapefile (*.shp)"
    else:
        name_filter = f"*.{file_type}"

    file_dialog.setNameFilter(name_filter)

    if file_dialog.exec():
        selected_files = file_dialog.selectedFiles()
        if selected_files:
            selected_file = selected_files[0]
            # The dialog should handle the extension, but as a fallback:
            if not selected_file.lower().endswith(f".{file_type}") and file_type != "ogr":
                if not os.path.splitext(selected_file)[1]:
                    selected_file += f".{file_type}"
            output_field.setText(selected_file)
