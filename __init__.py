# -*- coding: utf-8 -*-
"""
/***************************************************************************
 LeastCostPipeline
                                  A QGIS plugin
 Calculate least cost CO2 pipeline
 ***************************************************************************/
"""
from PyQt5.QtWidgets import QAction

from .src.analysis_dialog import AnalysisDialog

class LeastCostPipelinePlugin:
    def __init__(self, iface):
        self.iface = iface
        self.analysis_dialog = None
        self.analysis_action = None

    def initGui(self):
        # Action for "Analysis"
        self.analysis_action = QAction("Least Cost Pipeline", self.iface.mainWindow())
        self.analysis_action.triggered.connect(self.show_analysis_dialog)
        self.iface.addToolBarIcon(self.analysis_action)
        self.iface.pluginMenu().addAction(self.analysis_action)

    def unload(self):
        # Remove the actions from the menu and toolbar
        self.iface.pluginMenu().removeAction(self.analysis_action)
        self.iface.removeToolBarIcon(self.analysis_action)

    def show_analysis_dialog(self):
        # Show the Analysis dialog
        if not self.analysis_dialog:
            self.analysis_dialog = AnalysisDialog()
        self.analysis_dialog.show()
        
def classFactory(iface):
    return LeastCostPipelinePlugin(iface)