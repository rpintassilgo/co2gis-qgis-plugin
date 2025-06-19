from typing import Callable, TYPE_CHECKING
from qgis.core import QgsProject, QgsApplication, QgsMapLayer
from ..analysis.cost import clip_raster_to_vector, combine_rasters_with_qgis_raster_calculator, run_r_cost
from ..analysis.drain import run_r_drain_and_load
from ..complete_dialog.land_use import get_land_use_class_costs
from qgis.core import QgsTask, QgsMessageLog, QgsRasterLayer
from ..analysis.land_use import get_land_use_costs_raster
from ..analysis.dem import create_slope_costs_from_slope, create_slope_layer_from_dem
import os
from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsRasterLayer,
    QgsProcessingFeedback,
    QgsProcessing
)
from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsRasterLayer,
    QgsProcessingFeedback,
    QgsProcessing
)
from PyQt5.QtWidgets import QMessageBox
import processing
import os
from qgis.core import QgsVectorLayer, QgsVectorFileWriter, QgsProject, QgsFeature, QgsFields, QgsWkbTypes
from PyQt5.QtWidgets import QMessageBox
import processing

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
            self.run_logic(self.dialog)
            return True
        except Exception as e:
            return False

def run_step(dialog: 'StepByStepDialog', step_id: int, run_logic: Callable):
    """Runs a step with the specified logic."""
    task = RunStepTask(dialog, step_id, run_logic, f"Run Step {step_id}")
    QgsApplication.taskManager().addTask(task)
    QgsMessageLog.logMessage(f"Step {step_id} task added to Task Manager.")

# Step Logic Functions
def run_step1_logic(dialog: 'StepByStepDialog'):
    """Step 1: Create Land Use Costs Raster"""
    try:
        land_use_layer = QgsProject.instance().mapLayer(dialog.terrainComboBox.currentData())
        class_costs = get_land_use_class_costs(dialog)
        
        if not land_use_layer:
            raise ValueError("No land use layer selected.")

        output_path = dialog.costsRasterPath.text()
        if not output_path:
            raise ValueError("No output path specified for Land Use Costs Raster.")
        
        dialog.log_message("Creating Land Use Costs Raster...")
        get_land_use_costs_raster(land_use_layer, class_costs, dialog.costsRasterPath.text())
        dialog.log_message(f"Land Use Costs Raster created successfully at: {output_path}")
    except Exception as e:
        error_message = f"Createating Land Use Costs Raster Has Failed: {str(e)}"
        dialog.log_message(error_message)

def run_step2_logic(dialog: 'StepByStepDialog'):
    """Step 2: Create Slope Raster from DEM"""
    try:
        dem_layer = QgsProject.instance().mapLayer(dialog.demComboBox.currentData())

        if not dem_layer:
            raise ValueError("No DEM layer selected.")

        output_path = dialog.slopeRasterPath.text()
        if not output_path:
            raise ValueError("No output path specified for Slope Raster.")
        
        costs_outputh_path = dialog.slopeRasterPath.text()
        if not costs_outputh_path:
            raise ValueError("No output path specified for Slope Costs Raster.")

        dialog.log_message("Creating Slope Raster from DEM...")
        create_slope_layer_from_dem(dem_layer, output_path)
        dialog.log_message(f"Slope Raster created successfully at: {output_path}")
        
        # Load the raster layer from the path
        layer = QgsRasterLayer(output_path, "slope_layer")
        slope_layer = QgsProject.instance().addMapLayer(layer)

        if not slope_layer.isValid():
            raise RuntimeError(f"Invalid slope raster layer: {output_path}")
        
        slope_costs = dialog.get_slope_cost_intervals()
        dialog.log_message("Creating Slope Costs Raster from Slope Raster...")
        create_slope_costs_from_slope(slope_layer, slope_costs, costs_outputh_path)
        dialog.log_message(f"Slope Costs Raster created successfully at: {output_path}")
    except Exception as e:
        error_message = f"Creating Slope Raster from DEM Has Failed {str(e)}"
        dialog.log_message(error_message)


def run_step3_logic(dialog: 'StepByStepDialog'):
    """Step 3: Combine Land Use and Slope Rasters"""
    try:
        # Retrieve weight inputs
        occupancy_weight = float(dialog.landUseCostWeightInput.text().strip())
        dem_weight = float(dialog.slopeRasterWeightInput.text().strip())
        corridors_weight = float(dialog.slopeRasterWeightInput.text().strip())
        crossings_weight = float(dialog.slopeRasterWeightInput.text().strip())

        # Validate weights
        if occupancy_weight <= 0 or dem_weight <= 0 or corridors_weight <= 0 or crossings_weight <= 0:
            raise ValueError("All weights must be greater than zero.")

        # Retrieve selected layers
        costs_layer = QgsProject.instance().mapLayer(dialog.step3LandUseDropdown.currentData())
        slope_layer = QgsProject.instance().mapLayer(dialog.step3SlopeDropdown.currentData())
        corridors_layer = QgsProject.instance().mapLayer(dialog.step3CorridorsDropdown.currentData())
        crossings_layer = QgsProject.instance().mapLayer(dialog.step3CrossingsDropdown.currentData())

        if not costs_layer:
            raise ValueError("No Land Use Costs Raster selected.")
        if not slope_layer:
            raise ValueError("No Slope Raster selected.")
        if not corridors_layer:
            raise ValueError("No Corridors Raster selected.")
        if not crossings_layer:
            raise ValueError("No Crossings Raster selected.")

        # Retrieve output path
        output_path = dialog.combinedRasterPath.text().strip()
        if not output_path:
            raise ValueError("No output path specified for Combined Raster.")

        dialog.log_message("Combining Land Use Costs and Slope Rasters...")

        # Perform raster combination
        combine_rasters_with_qgis_raster_calculator(
            get_layer_path(costs_layer),
            get_layer_path(slope_layer),
            get_layer_path(corridors_layer),
            get_layer_path(crossings_layer),
            occupancy_weight,
            dem_weight,
            corridors_weight,
            crossings_weight,
            output_path
        )

        dialog.log_message(f"Combined Raster created successfully at: {output_path}")
    except ValueError as ve:
        error_message = f"Combining Cost Rasters Has Validation Errors: {str(ve)}"
        dialog.log_message(error_message)
    except Exception as e:
        error_message = f"Combining Cost Rasters Has Failed: {str(e)}"
        dialog.log_message(error_message)


def run_step4_logic(dialog: 'StepByStepDialog'):
    """Step 4: Clip Combined Raster"""
    try:
        points_layer = QgsProject.instance().mapLayer(dialog.clipPointVectorComboBox.currentData())
        combined_layer = QgsProject.instance().mapLayer(dialog.step4Dropdown.currentData())

        if not points_layer:
            raise ValueError("No points layer selected.")

        if not combined_layer:
            raise ValueError("No combined raster layer selected.")

        output_path = dialog.clippedRasterPath.text().strip()
        if not output_path:
            raise ValueError("No output path specified for Clipped Raster.")

        dialog.log_message("Clipping Combined Raster to Area...")
        clip_raster_to_vector(get_layer_path(combined_layer), points_layer, output_path)
        dialog.log_message(f"Clipped Combined Raster created successfully at: {output_path}")
        
        # ✅ Copy Symbology if checkbox is checked
        if dialog.copySymbologyCheckbox.isChecked():
            dialog.log_message("Copying symbology from original raster...")
            apply_symbology(combined_layer, output_path)
            dialog.log_message("Symbology copied successfully.")

    except ValueError as ve:
        error_message = f"Clipping Combined Raster to Area Has Validation Errors: {str(ve)}"
        dialog.log_message(error_message)
    except Exception as e:
        error_message = f"Clipping Combined Raster to Area Has Failed: {str(e)}"
        dialog.log_message(error_message)

def run_step5_logic(dialog: 'StepByStepDialog'):
    """Step 5: Generate Least Cost Path Vector"""
    try:
        points_layer = QgsProject.instance().mapLayer(dialog.pointsComboBox.currentData())
        combined_layer = QgsProject.instance().mapLayer(dialog.step5Dropdown.currentData())

        if not points_layer:
            raise ValueError("No points layer selected.")
        if not combined_layer:
            raise ValueError("No combined raster layer selected.")

        cost_output_path = dialog.costRasterPath.text().strip()
        direction_output_path = dialog.directionRasterPath.text().strip()
        drain_output_path = dialog.drainRasterPath.text().strip()
        vector_output_path = dialog.finalPath.text().strip()

        if not cost_output_path:
            raise ValueError("No output path specified for Cost Raster.")
        if not direction_output_path:
            raise ValueError("No output path specified for Direction Raster.")
        if not drain_output_path:
            raise ValueError("No output path specified for Drain Raster.")
        if not vector_output_path:
            raise ValueError("No output path specified for Least Cost Path Vector.")

        dialog.log_message("Running r.cost to compute cost surface...")
        cost_result = run_r_cost(combined_layer, points_layer, cost_output_path, direction_output_path)
        dialog.log_message(f"r.cost completed successfully.")

        dialog.log_message("Running r.drain and converting to vector...")
        run_r_drain_and_load(cost_result, points_layer, drain_output_path, vector_output_path)
        dialog.log_message(f"Least Cost Path Vector generated successfully at: {vector_output_path}")

    except ValueError as ve:
        dialog.log_message(f"Validation Error: {str(ve)}")
    except Exception as e:
        dialog.log_message(f"Process Failed: {str(e)}")

def run_step_resample(dialog: 'StepByStepDialog'):
    """Step 6: Resample Raster"""
    try:
        raster_layer = QgsProject.instance().mapLayer(dialog.resampleRasterComboBox.currentData())

        if not raster_layer:
            raise ValueError("No raster selected for resampling.")

        target_resolution = dialog.targetResolutionInput.text().strip()
        if not target_resolution:
            raise ValueError("No target resolution specified.")

        try:
            target_resolution = float(target_resolution)
            if target_resolution <= 0:
                raise ValueError("Target resolution must be a positive number.")
        except ValueError:
            raise ValueError("Invalid target resolution. Please enter a numerical value.")

        resampling_method = dialog.resamplingMethodComboBox.currentText()
        output_path = dialog.resampleOutputPath.text().strip()
        if not output_path:
            raise ValueError("No output path specified for Resampled Raster.")

        dialog.log_message(f"Resampling raster '{raster_layer.name()}' to {target_resolution} meters using {resampling_method} method...")

        # Perform resampling using QGIS processing tools
        params = {
            'INPUT': raster_layer,
            'TARGET_RESOLUTION': target_resolution,
            'RESAMPLING_METHOD': resampling_method.lower().replace(" ", "_"),
            'OUTPUT': output_path
        }

        from qgis import processing
        processing.run("gdal:warpreproject", params)

        dialog.log_message(f"Resampled raster saved successfully at: {output_path}")

    except ValueError as ve:
        error_message = f"Resampling Raster Validation Error: {str(ve)}"
        dialog.log_message(error_message)
    except Exception as e:
        error_message = f"Resampling Raster Failed: {str(e)}"
        dialog.log_message(error_message)

def run_step7_logic(dialog: 'StepByStepDialog'):
    """Step 7: Create Cost Raster from Vector"""
    try:
        vector_layer = QgsProject.instance().mapLayer(dialog.vectorRasterComboBox.currentData())
        output_path = dialog.vectorRasterOutputPath.text().strip()
        cost_with_vector = dialog.hasVectorCostInput.text().strip()
        cost_without_vector = dialog.hasNotVectorCostInput.text().strip()

        if not vector_layer or not output_path or not cost_with_vector or not cost_without_vector:
            raise ValueError("Missing inputs. Please select a vector layer, enter costs, and set an output path.")

        try:
            cost_with_vector = float(cost_with_vector)
            cost_without_vector = float(cost_without_vector)
        except ValueError:
            raise ValueError("Costs must be valid numeric values.")

        feedback = QgsProcessingFeedback()

        dialog.log_message("Creating cost raster from vector...")
        
        ref_layer_id = dialog.refRasterComboBox.currentData()
        ref_raster = QgsProject.instance().mapLayer(ref_layer_id)

        if not isinstance(ref_raster, QgsRasterLayer):
            raise ValueError("Please select a valid reference raster.")

        pixel_size = 10.0  # or 30.0 depending on your use case
        extent = ref_raster.extent()
        width = 10
        height = 10

        dialog.log_message(f"Pixel size X: {ref_raster.rasterUnitsPerPixelX()}")
        dialog.log_message(f"Pixel size Y: {ref_raster.rasterUnitsPerPixelY()}")
        dialog.log_message(f"custo com vetor: {cost_with_vector}")
        dialog.log_message(f"custo sem vetor: {cost_without_vector}")
        dialog.log_message(f"width: {width}")
        dialog.log_message(f"height: {height}")
        dialog.log_message(f"teste: {(extent.xMaximum() - extent.xMinimum())}")

        # Rasterize
        rasterized_output = processing.run("gdal:rasterize", {
            'INPUT': vector_layer,
            'FIELD': None,
            'BURN': cost_with_vector,
            'UNITS': 1,
            'WIDTH': width,
            'HEIGHT': height,
            'EXTENT': extent,
            'INIT': cost_without_vector,
            'DATA_TYPE': 5,  # Float32
            'OUTPUT': output_path
        }, feedback=feedback)


        if rasterized_output and 'OUTPUT' in rasterized_output:
            dialog.log_message(f"Cost raster created successfully at: {rasterized_output['OUTPUT']}")
            new_raster = QgsRasterLayer(rasterized_output['OUTPUT'], "Cost Raster from Vector")
            if new_raster.isValid():
                QgsProject.instance().addMapLayer(new_raster)
            else:
                raise RuntimeError("Output raster is invalid.")
        else:
            raise RuntimeError("Rasterization failed without output.")
    except Exception as e:
        dialog.log_message(f"Step 7 Failed: {str(e)}")

def run_step8_logic(dialog: 'StepByStepDialog'):
    """Step 8: Combine two vector layers into one"""
    try:
        layer1_id = dialog.vectorComboBox.currentData()
        layer2_id = dialog.vector2ComboBox.currentData()
        output_path = dialog.vectorsOutputPath.text().strip()

        if not layer1_id or not layer2_id or not output_path:
            raise ValueError("Please select two vector layers and specify an output path.")

        layer1 = QgsProject.instance().mapLayer(layer1_id)
        layer2 = QgsProject.instance().mapLayer(layer2_id)

        if not isinstance(layer1, QgsVectorLayer) or not isinstance(layer2, QgsVectorLayer):
            raise TypeError("Selected layers are not valid vector layers.")

        if layer1.geometryType() != layer2.geometryType():
            raise ValueError("Both vectors must have the same geometry type.")

        fields = layer1.fields()
        geometry_type = layer1.wkbType()
        crs = layer1.crs()

        writer = QgsVectorFileWriter(output_path, 'UTF-8', fields, geometry_type, crs, 'ESRI Shapefile')

        if writer.hasError() != QgsVectorFileWriter.NoError:
            raise IOError(f"Error writing file: {writer.errorMessage()}")

        for layer in [layer1, layer2]:
            for feature in layer.getFeatures():
                writer.addFeature(QgsFeature(feature))

        del writer  # Finalize writing

        dialog.log_message("Step 8: Vectors combined and saved successfully.")

        if os.path.exists(output_path):
            combined_layer = QgsVectorLayer(output_path, "Combined Vectors", "ogr")
            if combined_layer.isValid():
                QgsProject.instance().addMapLayer(combined_layer)
                dialog.log_message("Combined layer added to map.")
            else:
                raise RuntimeError("The output combined vector layer is invalid.")

    except Exception as e:
        dialog.log_message(f"Step 8 Failed: {str(e)}")

def run_slope_costs_logic(dialog: 'StepByStepDialog'):
    """Create slope costs raster based on defined intervals."""
    try:
        # Get slope intervals from the table
        intervals = dialog.get_slope_cost_intervals()
        if not intervals:
            raise ValueError("No slope intervals defined.")

        # Get the slope layer from the dropdown
        slope_layer = QgsProject.instance().mapLayer(dialog.slopeLayerComboBox.currentData())
        if not slope_layer or not slope_layer.isValid():
            raise ValueError("Please select a valid slope layer.")
        
        # Get output path from UI
        output_path = dialog.slopeCostsRasterPath.text()
        if not output_path:
            raise ValueError("No output path specified for Slope Costs Raster.")
        
        dialog.log_message("Creating Slope Costs Raster...")
        create_slope_costs_from_slope(slope_layer, intervals, output_path)
        dialog.log_message(f"Slope Costs Raster created successfully at: {output_path}")
        
        # Load the created raster into QGIS
        new_layer = QgsRasterLayer(output_path, "Slope Costs")
        if new_layer.isValid():
            QgsProject.instance().addMapLayer(new_layer)
        else:
            dialog.log_message("Warning: Created raster could not be loaded into QGIS.")
            
    except Exception as e:
        error_message = f"Creating Slope Costs Raster Has Failed: {str(e)}"
        dialog.log_message(error_message)

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

def apply_symbology(original_layer, clipped_path):
    """Applies symbology from the original raster to the clipped raster without adding it to QGIS."""
    if not original_layer or not clipped_path:
        raise ValueError("Layers are None")

    # Define temporary QML style file
    style_path = os.path.splitext(clipped_path)[0] + ".qml"

    # Save original layer symbology to QML file
    original_layer.saveNamedStyle(style_path)

    # Load clipped raster layer (but NOT add it to the project)
    clipped_layer = QgsRasterLayer(clipped_path, "Clipped Raster", "gdal")

    if clipped_layer.isValid():
        # Apply saved QML symbology to the clipped raster
        clipped_layer.loadNamedStyle(style_path)
        clipped_layer.triggerRepaint()  # Ensure it updates