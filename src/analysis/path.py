from qgis.core import QgsApplication
import os

def get_plugin_output_path(filename):
    """Generate a dynamic output path in a plugin-specific directory."""
   # plugin_dir = os.path.join(QgsApplication.qgisSettingsDirPath(), "least_cost_path")
   # since i dont have space on my pc im storing it in an external hard drive
    plugin_dir = os.path.join("/Volumes/rodrigo/ficheiros", "least_cost_path")
    if not os.path.exists(plugin_dir):
        os.makedirs(plugin_dir)
    return os.path.join(plugin_dir, filename)
