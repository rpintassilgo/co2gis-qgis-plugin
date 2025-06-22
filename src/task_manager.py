from typing import Callable, TYPE_CHECKING
from qgis.core import QgsTask, QgsApplication, QgsMessageLog
from PyQt5.QtWidgets import QMessageBox

if TYPE_CHECKING:
    from .analysis_dialog import AnalysisDialog

class AnalysisTask(QgsTask):
    """Generic task class for executing analysis logic asynchronously."""
    
    def __init__(self, dialog: 'AnalysisDialog', logic_function: Callable, description="Running Analysis"):
        super().__init__(description, QgsTask.CanCancel)
        self.dialog = dialog
        self.logic_function = logic_function
        self.exception = None

    def run(self):
        try:
            self.logic_function(self.dialog)
            return True
        except Exception as e:
            self.exception = e
            return False

    def finished(self, result):
        if not result and self.exception:
            QMessageBox.critical(self.dialog, "Error", f"An error occurred: {self.exception}")
            self.dialog.log_message(f"Error: {self.exception}")

def run_analysis(dialog: 'AnalysisDialog', logic_function: Callable):
    """Runs a piece of analysis logic in a background task."""
    task_name = logic_function.__name__
    task_description = f"Running: {task_name.replace('_', ' ').title()}"
    task = AnalysisTask(dialog, logic_function, task_description)
    QgsApplication.taskManager().addTask(task)
    dialog.log_message(f"Task '{task_description}' started.")
