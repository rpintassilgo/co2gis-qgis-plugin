# -*- coding: utf-8 -*-
"""
/***************************************************************************
 LeastCostPipeline
                                  A QGIS plugin
 Calculate least cost CO2 pipeline
 ***************************************************************************/
"""
from PyQt5.QtWidgets import QAction

from .src.step_dialog import StepByStepDialog

class LeastCostPipelinePlugin:
    def __init__(self, iface):
        self.iface = iface
        self.step_dialog = None
        self.step_by_step_action = None

    def initGui(self):
        # Action for "Step-by-Step Analysis"
        self.step_by_step_action = QAction("Least Cost Pipeline", self.iface.mainWindow())
        self.step_by_step_action.triggered.connect(self.show_step_dialog)
        self.iface.addToolBarIcon(self.step_by_step_action)
        self.iface.pluginMenu().addAction(self.step_by_step_action)

    def unload(self):
        # Remove the actions from the menu and toolbar
        self.iface.pluginMenu().removeAction(self.step_by_step_action)
        self.iface.removeToolBarIcon(self.step_by_step_action)

    def show_step_dialog(self):
        # Show the Step-by-Step Analysis dialog
        if not self.step_dialog:
            self.step_dialog = StepByStepDialog()
        self.step_dialog.show()
        
def classFactory(iface):
    return LeastCostPipelinePlugin(iface)