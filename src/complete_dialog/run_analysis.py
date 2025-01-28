from typing import TYPE_CHECKING
from PyQt5.QtWidgets import ( QMessageBox )
from qgis.core import QgsProject, QgsRasterLayer, QgsApplication
from ..analysis.cost import clip_raster_to_vector, combine_rasters_with_qgis_raster_calculator, combine_rasters_with_qgis_raster_calculator, run_r_cost
from ..analysis.drain import run_r_drain_and_load
from ..complete_dialog.land_use import get_land_use_class_costs
from qgis.core import QgsTask, QgsMessageLog
from ..analysis.path import get_plugin_output_path
from ..analysis.land_use import get_land_use_costs_raster
from ..analysis.dem import create_slope_layer_from_dem

if TYPE_CHECKING:
    from ..complete_dialog import Dialog

# Note: For what I've seen tasks in QGIS plugins are broken, it is necessary to log a message with QgsMessageLog
# to run the task added to task manager, and it never enters finished function inside the task. So I'm using
# a signal as a work around.
# https://gis.stackexchange.com/questions/407727/qgstask-finished-function-isnt-executed

class RunAnalysisTask(QgsTask):
    def __init__(self, dialog, description="Run Analysis"):
        super().__init__(description, QgsTask.CanCancel)
        self.dialog: 'Dialog' = dialog
        self.class_costs = None

    def run(self):
        try:
            class_costs_raster_path = get_plugin_output_path("land_use_costs_raster.tif")
            dem_slope_path = get_plugin_output_path("dem_slope.tif")
            combined_raster_path = get_plugin_output_path("combined_raster.tif")
            clipped_combined_raster_path = get_plugin_output_path("clipped_combined_raster.tif")
            vector_output_path = get_plugin_output_path("least_cost_path.gpkg")
            
            self.dialog.log_message("Starting analysis...")
            
            # Gather inputs
            dem_weight, occupancy_weight = self.dialog.get_weights()
            land_use_layer, dem_layer, points_layer = self.dialog.get_layers()
            self.class_costs = get_land_use_class_costs(self.dialog)
            
            # generate land use costs raster
            self.dialog.log_message("Building land use raster with costs...")
            get_land_use_costs_raster(land_use_layer, self.class_costs, class_costs_raster_path)
            self.dialog.log_message(f"Land use raster with costs created in path: {class_costs_raster_path}")
            
            # create slope raster from dem
            self.dialog.log_message("Creating slope raster from DEM...")
            create_slope_layer_from_dem(self.dialog, dem_layer, dem_slope_path)
            self.dialog.log_message(f"Slope raster created at: {dem_slope_path}")
            
            # combine slope and class costs rasters
            self.dialog.log_message("Creating combined raster from both rasters....")
            combine_rasters_with_qgis_raster_calculator(class_costs_raster_path,dem_slope_path, occupancy_weight, dem_weight,combined_raster_path)
            self.dialog.log_message(f"Combined raster created at: {combined_raster_path}")           
            
            # clip relevant area from combined raster
            self.dialog.log_message("Clipping combined raster to relevant area...")
            clip_raster_to_vector(self.dialog, combined_raster_path, points_layer, clipped_combined_raster_path)
            
            # add clipped combined raster to qgis project
            clipped_combined_raster = QgsRasterLayer(clipped_combined_raster_path, "Clipped Combined Raster")
            QgsProject.instance().addMapLayer(clipped_combined_raster)
            
            # use output on r.cost
            self.dialog.log_message("Running r.cost...")
            cost_result = run_r_cost(self.dialog, clipped_combined_raster, points_layer)
            self.dialog.log_message("r.cost completed.")
            
            # Run r.drain and load the result
            self.dialog.log_message("Running r.drain and converting to vector...")
            run_r_drain_and_load(cost_result, points_layer, vector_output_path)
            self.dialog.log_message("r.drain and vector conversion completed.")

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


def acabou(exception, value=None):
    if not exception:
        print("ACABOUUU")
    else:
        print("DEU ERRO")

def run_analysis(dialog: 'Dialog'):
    if not dialog.all_fields_valid():
        QMessageBox.warning(dialog, "Invalid Input", "Please fill in all required fields and ensure at least one cost is greater than 0.")
        return

    task = RunAnalysisTask(dialog)
    QgsApplication.taskManager().addTask(task)
    
    # Work around - https://github.com/qgis/QGIS/issues/37655 
    QgsMessageLog.logMessage('test')

