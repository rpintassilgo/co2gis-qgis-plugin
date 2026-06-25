# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QAction

from .src.analysis_dialog import AnalysisDialog


class CO2GISPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.analysis_dialog = None
        self.analysis_action = None

    def initGui(self):
        self.analysis_action = QAction("CO2GIS", self.iface.mainWindow())
        self.analysis_action.triggered.connect(self.show_analysis_dialog)
        self.iface.addToolBarIcon(self.analysis_action)
        self.iface.pluginMenu().addAction(self.analysis_action)

    def unload(self):
        self.iface.pluginMenu().removeAction(self.analysis_action)
        self.iface.removeToolBarIcon(self.analysis_action)

    def show_analysis_dialog(self):
        if not self.analysis_dialog:
            self.analysis_dialog = AnalysisDialog()
        self.analysis_dialog.show()


def classFactory(iface):
    return CO2GISPlugin(iface)
