from typing import Callable, TYPE_CHECKING
from qgis.core import QgsProject, QgsApplication, QgsMapLayer
from ..analysis.cost import clip_raster_to_vector, combine_rasters_with_qgis_raster_calculator, run_r_cost
from ..analysis.drain import run_r_drain_and_load
from ..complete_dialog.land_use import get_land_use_class_costs
from qgis.core import QgsTask, QgsMessageLog
from ..analysis.land_use import get_land_use_costs_raster
from ..analysis.dem import create_slope_layer_from_dem

if TYPE_CHECKING:
    from . import StepByStepDialog

class RunStepTask(QgsTask):
    """Generic task class for executing steps asynchronously."""
    
    def __init__(self, dialog, step_id, run_logic: Callable, description="Run Step"):
        super().__init__(description, QgsTask.CanCancel)
        self.dialog: 'StepByStepDialog' = dialog
        self.step_id = step_id
        self.run_logic = run_logic

    def run(self):
        try:
            self.dialog.log_message(f"Starting Step {self.step_id}...")
            self.run_logic(self.dialog)
            self.dialog.log_message(f"Step {self.step_id} completed successfully.")
            return True
        except Exception as e:
            self.dialog.log_message(f"Step {self.step_id} failed: {str(e)}")
            return False

def run_step(dialog: 'StepByStepDialog', step_id: int, run_logic: Callable):
    """Runs a step with the specified logic."""
    task = RunStepTask(dialog, step_id, run_logic, f"Run Step {step_id}")
    QgsApplication.taskManager().addTask(task)
    QgsMessageLog.logMessage(f"Step {step_id} task added to Task Manager.")

# Step Logic Functions
def run_step1_logic(dialog: 'StepByStepDialog'):
    """Step 1: Create Land Use Costs Raster"""
    land_use_layer = QgsProject.instance().mapLayer(dialog.terrainComboBox.currentData())
    class_costs = get_land_use_class_costs(dialog)
    get_land_use_costs_raster(land_use_layer, class_costs, dialog.costsRasterPath.text())

def run_step2_logic(dialog: 'StepByStepDialog'):
    """Step 2: Create Slope Raster from DEM"""
    dem_layer = QgsProject.instance().mapLayer(dialog.demComboBox.currentData())
    create_slope_layer_from_dem(dialog, dem_layer, dialog.slopeRasterPath.text())

def run_step3_logic(dialog: 'StepByStepDialog'):
    """Step 3: Combine Land Use and Slope Rasters"""
    dem_weight = float(dialog.slopeRasterWeightInput.text())
    occupancy_weight = float(dialog.landUseCostWeightInput.text())

    costs_layer = QgsProject.instance().mapLayer(dialog.step3LandUseDropdown.currentData())
    slope_layer = QgsProject.instance().mapLayer(dialog.step3SlopeDropdown.currentData())

    combine_rasters_with_qgis_raster_calculator(
        get_layer_path(costs_layer),
        get_layer_path(slope_layer),
        occupancy_weight,
        dem_weight,
        dialog.combinedRasterPath.text()
    )

def run_step4_logic(dialog: 'StepByStepDialog'):
    """Step 4: Clip Combined Raster"""
    points_layer = QgsProject.instance().mapLayer(dialog.pointsComboBox.currentData())
    combined_layer = QgsProject.instance().mapLayer(dialog.step4Dropdown.currentData())

    clip_raster_to_vector(dialog, get_layer_path(combined_layer), points_layer, dialog.clippedRasterPath.text())

def run_step5_logic(dialog: 'StepByStepDialog'):
    """Step 5: Generate Least Cost Path Vector"""
    points_layer = QgsProject.instance().mapLayer(dialog.pointsComboBox.currentData())
    clipped_combined_layer = QgsProject.instance().mapLayer(dialog.step5Dropdown.currentData())

    cost_result = run_r_cost(dialog, clipped_combined_layer, points_layer)
    run_r_drain_and_load(cost_result, points_layer, dialog.finalPath.text())

def get_layer_path(layer):
    """Returns the file path of the given QgsMapLayer."""
    if layer is None:
        raise ValueError("Layer is None. Please check your selection.")

    data_provider = layer.dataProvider()
    if not data_provider:
        raise ValueError("Layer does not have a valid data provider.")

    uri = data_provider.dataSourceUri()

    if layer.type() == QgsMapLayer.RasterLayer:
        return uri
    if layer.type() == QgsMapLayer.VectorLayer:
        return uri.split("|")[0]
    
    raise ValueError("Unsupported layer type. Only Raster and Vector layers are supported.")
