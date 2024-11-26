from typing import TYPE_CHECKING
from PyQt5.QtCore import (Qt, pyqtSignal)
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QComboBox, QTableWidget, 
    QTableWidgetItem, QLineEdit, QPushButton, QHBoxLayout, 
    QFormLayout, QHeaderView, QTextEdit, QTabWidget, QMessageBox
)
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer, QgsPalettedRasterRenderer, QgsApplication
from .cost import run_r_cost, combine_rasters_with_weights
from .drain import run_r_drain
from ..dialog.land_use import get_land_use_class_costs
from qgis.core import QgsTask, QgsMessageLog, Qgis
from .path import get_plugin_output_path
from .land_use import get_land_use_costs_raster
from .dem import create_slope_layer_from_dem

if TYPE_CHECKING:
    from ..dialog import Dialog


# Note: For what I've seen tasks in QGIS plugins are broken, it is necessary to log a message with QgsMessageLog
# to run the task added to task manager, and it never enters finished function inside the task. So I'm using
# a signal as a work around.
# https://gis.stackexchange.com/questions/407727/qgstask-finished-function-isnt-executed
class MinimalTask(QgsTask):
    def __init__(self, dialog, description="Minimal Task"):
        print("ENTROU NO INIT MINIMAL TASK")
        super().__init__(description, QgsTask.CanCancel)
        self.dialog = dialog
        self.dialog.log_message("ENTROU NO INIT MINIMAL TASK")

    def run(self):
        try:
            print("ENTROU NO RUN DA MINIMAL TASK")
            self.dialog.log_message("Minimal Task is running...")
            return True
        except Exception as e:
            print(f"RUN ERROR: {e}")
            self.dialog.log_message(f"Error in run(): {e}")
            return False

    def finished(self, result):
        print("entrou no finished")
        self.dialog.log_message("--- ACABOUUUU")
        if result:
            self.dialog.log_message("Minimal Task completed successfully.")
        else:
            self.dialog.log_message("Minimal Task failed.")

class DebugTask(QgsTask):
    def __init__(self, dialog, description="Run Analysis"):
        super().__init__(description, QgsTask.CanCancel)
        self.dialog: 'Dialog' = dialog
        self.class_costs = None

    def run(self):
        try:
            self.dialog.log_message("Starting debug...")
            
            _, _, points_layer = self.dialog.get_layers()
            
            class_costs_raster = "/Volumes/rodrigo/ficheiros/least_cost_path/land_use_costs_raster.tif"
            dem_slope = "/Volumes/rodrigo/ficheiros/least_cost_path/land_use_costs_raster.tif"
            
            # raster calculator with defined weights
            combined_raster_path = get_plugin_output_path("combined_raster.tif")
            combined_raster = combine_rasters_with_weights(
                self.dialog, 
                class_costs_raster, 
                dem_slope, 
                self.dialog.demWeightInput,
                self.dialog.occupancyWeightInput,
                combined_raster_path
            )
            
            # use output on r.cost
            self.dialog.log_message("Running r.cost...")
            cost_result = run_r_cost(combined_raster, points_layer)
            self.dialog.log_message("r.cost completed.")
            print(f"r.cost output: {cost_result['output']}")
            
            self.dialog.log_message("Running r.drain...")
            drain_result = run_r_drain(cost_result, points_layer)
            self.dialog.log_message("r.drain completed.")
            print(f"r.drain output: {drain_result['output']}")

            # add result to map
            #QgsProject.instance().addMapLayer(drain_result['output'])
            self.dialog.log_message("Least-cost path added to map.")
            return True
        except Exception as e:
            self.dialog.log_message(f"Error: {str(e)}")
            return False

    def finished(self, result):
        print("ENTROU NO FINISHED")
        if result:
            self.dialog.log_message("Analysis completed successfully.")
        else:
            self.dialog.log_message("Analysis failed.")

    def cancel(self):
        self.dialog.log_message("Task canceled.")
        super().cancel()


class RunAnalysisTask(QgsTask):
    def __init__(self, dialog, description="Run Analysis"):
        super().__init__(description, QgsTask.CanCancel)
        self.dialog: 'Dialog' = dialog
        self.class_costs = None

    def run(self):
        try:
            self.dialog.log_message("Starting analysis...")
            
            # gather inputs
            dem_weight, occupancy_weight = self.dialog.get_weights()
            land_use_layer, dem_layer, points_layer = self.dialog.get_layers()
            self.class_costs = get_land_use_class_costs(self.dialog)
            
            # raster calculator on land user layer
            # todo: maybe pass logs inside get land use costs raster function
            # like i did with create_slope_layer_from_dem to make the code more readable
            self.dialog.log_message("Building land use raster with costs...")
            class_costs_raster_path = get_plugin_output_path("land_use_costs_raster.tif")
            class_costs_raster = get_land_use_costs_raster(land_use_layer, self.class_costs, class_costs_raster_path)
            self.dialog.log_message(f"Land use raster with costs created in path: {class_costs_raster}")
            
            # create slope based on dem
            dem_slope_path = get_plugin_output_path("dem_slope.tif")
            dem_slope = create_slope_layer_from_dem(self.dialog, dem_layer, dem_slope_path)
            
            # raster calculator with defined weights
            combined_raster_path = get_plugin_output_path("combined_raster.tif")
            combined_raster = combine_rasters_with_weights(
                self.dialog, 
                class_costs_raster, 
                dem_slope, 
                self.dialog.demWeightInput,
                self.dialog.occupancyWeightInput,
                combined_raster_path
            )
            
            # use output on r.cost
            self.dialog.log_message("Running r.cost...")
            cost_result = run_r_cost(combined_raster, points_layer)
            self.dialog.log_message("r.cost completed.")
            print(f"r.cost output: {cost_result['output']}")
            
            self.dialog.log_message("Running r.drain...")
            drain_result = run_r_drain(cost_result, points_layer)
            self.dialog.log_message("r.drain completed.")
            print(f"r.drain output: {drain_result['output']}")

            # add result to map
            #QgsProject.instance().addMapLayer(drain_result['output'])
            self.dialog.log_message("Least-cost path added to map.")
            return True
        except Exception as e:
            self.dialog.log_message(f"Error: {str(e)}")
            return False

    def finished(self, result):
        print("ENTROU NO FINISHED")
        if result:
            self.dialog.log_message("Analysis completed successfully.")
        else:
            self.dialog.log_message("Analysis failed.")

    def cancel(self):
        self.dialog.log_message("Task canceled.")
        super().cancel()

def teste(task):
    return 5*6

def acabou(exception, value=None):
    if not exception:
        print("ACABOUUU")
    else:
        print("DEU ERRO")

def run_analysis(dialog: 'Dialog'):
    dialog.log_message("ENTROU NO RUN ANALYSIS")
    if not dialog.all_fields_valid():
        QMessageBox.warning(dialog, "Invalid Input", "Please fill in all required fields and ensure at least one cost is greater than 0.")
        return

    dialog.log_message("PASSOU O RETURN")
    task = RunAnalysisTask(dialog)
    #minimalTask = MinimalTask(dialog)
    #testeTask = QgsTask.fromFunction('task', teste, on_finished=acabou)
    QgsApplication.taskManager().addTask(task)
    
    # Work around - https://github.com/qgis/QGIS/issues/37655 
    QgsMessageLog.logMessage('test')

