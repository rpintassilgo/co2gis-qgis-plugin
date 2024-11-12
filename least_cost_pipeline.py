from PyQt5.QtWidgets import QAction
from .least_cost_pipeline_dialog import LeastCostPipelineDialog

class LeastCostPipelinePlugin:
    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.action = None

    def initGui(self):
        # Add an action to QGIS toolbar or menu
        self.action = QAction("Least Cost Pipeline", self.iface.mainWindow())
        self.action.triggered.connect(self.show_dialog)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("&Least Cost Pipeline", self.action)

    def unload(self):
        # Remove the action from QGIS when the plugin is unloaded
        self.iface.removePluginMenu("&Least Cost Pipeline", self.action)
        self.iface.removeToolBarIcon(self.action)

    def show_dialog(self):
        # Show the main dialog
        if not self.dialog:
            self.dialog = LeastCostPipelineDialog()
        self.dialog.show()
