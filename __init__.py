# -*- coding: utf-8 -*-
from qgis.PyQt.QtWidgets import QAction

from .src.analysis_dialog import AnalysisDialog
from .src.task_manager import cancel_tasks_for_dialog


class CO2GISPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.analysis_dialog = None
        self.analysis_action = None

    def initGui(self):
        self.analysis_action = QAction("CO2GIS", self.iface.mainWindow())
        self.analysis_action.setObjectName("CO2GISAnalysisAction")
        self.analysis_action.triggered.connect(self.show_analysis_dialog)
        self.iface.addToolBarIcon(self.analysis_action)
        self.iface.pluginMenu().addAction(self.analysis_action)

    def unload(self):
        # Dispose the dialog and disconnect its global signals to avoid ghost UI
        # and a dangling layersAdded connection after reload/disable.
        if self.analysis_dialog is not None:
            # Cancel in-flight tasks first, so none touches the dialog after it is deleted.
            cancel_tasks_for_dialog(self.analysis_dialog)
            self.analysis_dialog.cleanup()
            self.analysis_dialog.close()
            self.analysis_dialog.deleteLater()
            self.analysis_dialog = None

        self.iface.pluginMenu().removeAction(self.analysis_action)
        self.iface.removeToolBarIcon(self.analysis_action)
        self.analysis_action = None

    def show_analysis_dialog(self):
        if not self.analysis_dialog:
            self.analysis_dialog = AnalysisDialog(self.iface.mainWindow())
        self.analysis_dialog.show()


def classFactory(iface):
    return CO2GISPlugin(iface)
