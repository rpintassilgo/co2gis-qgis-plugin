# -*- coding: utf-8 -*-
"""
/***************************************************************************
 LeastCostPipeline
                                  A QGIS plugin
 Calculate least cost co2 pipeline
 ***************************************************************************/
"""
from PyQt5.QtWidgets import QAction
from .src.dialog import Dialog

class LeastCostPipelinePlugin:
    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.action = None

    def initGui(self):
        self.action = QAction("Least Cost Pipeline", self.iface.mainWindow())
        self.action.triggered.connect(self.show_dialog)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("&Least Cost Pipeline", self.action)

    def unload(self):
        self.iface.removePluginMenu("&Least Cost Pipeline", self.action)
        self.iface.removeToolBarIcon(self.action)

    def show_dialog(self):
        if not self.dialog:
            self.dialog = Dialog()
        self.dialog.show()
        
def classFactory(iface):
    return LeastCostPipelinePlugin(iface)
