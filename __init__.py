# -*- coding: utf-8 -*-
"""
/***************************************************************************
 LeastCostPipeline
                                  A QGIS plugin
 Calculate least cost CO2 pipeline
 ***************************************************************************/
"""
from PyQt5.QtWidgets import QAction

from .src.pipeline_costs import PipelineCostsDialog
from .src.complete_dialog import Dialog
from .src.step_dialog import StepByStepDialog

class LeastCostPipelinePlugin:
    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.step_dialog = None
        self.pipeline_costs_dialog = None
        self.complete_analysis_action = None
        self.step_by_step_action = None
        self.pipeline_costs_action = None

    def initGui(self):
        # Action for "Complete Analysis"
        self.complete_analysis_action = QAction("Complete Analysis", self.iface.mainWindow())
        self.complete_analysis_action.triggered.connect(self.show_dialog)
        self.iface.addToolBarIcon(self.complete_analysis_action)
        self.iface.addPluginToMenu("&Least Cost Pipeline", self.complete_analysis_action)

        # Action for "Step-by-Step Analysis"
        self.step_by_step_action = QAction("Step-by-Step Analysis", self.iface.mainWindow())
        self.step_by_step_action.triggered.connect(self.show_step_dialog)
        self.iface.addToolBarIcon(self.step_by_step_action)
        self.iface.addPluginToMenu("&Least Cost Pipeline", self.step_by_step_action)
        
        # Action for "Pipeline Costs"
        self.pipeline_costs_action = QAction("Pipeline Price Costs", self.iface.mainWindow())
        self.pipeline_costs_action.triggered.connect(self.show_pipeline_costs_dialog)
        self.iface.addToolBarIcon(self.pipeline_costs_action)
        self.iface.addPluginToMenu("&Least Cost Pipeline", self.pipeline_costs_action)

    def unload(self):
        # Remove the actions from the menu and toolbar
        self.iface.removePluginMenu("&Least Cost Pipeline", self.complete_analysis_action)
        self.iface.removeToolBarIcon(self.complete_analysis_action)

        self.iface.removePluginMenu("&Least Cost Pipeline", self.step_by_step_action)
        self.iface.removeToolBarIcon(self.step_by_step_action)
        
        self.iface.removePluginMenu("&Least Cost Pipeline", self.pipeline_costs_action)
        self.iface.removeToolBarIcon(self.pipeline_costs_action)


    def show_dialog(self):
        # Show the Complete Analysis dialog
        if not self.dialog:
            self.dialog = Dialog()
        self.dialog.show()

    def show_step_dialog(self):
        # Show the Step-by-Step Analysis dialog
        if not self.step_dialog:
            self.step_dialog = StepByStepDialog()
        self.step_dialog.show()
        
    def show_pipeline_costs_dialog(self):
        if not self.pipeline_costs_dialog:
            self.pipeline_costs_dialog = PipelineCostsDialog()
        self.pipeline_costs_dialog.show()

def classFactory(iface):
    return LeastCostPipelinePlugin(iface)