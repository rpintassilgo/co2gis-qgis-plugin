from typing import Callable, TYPE_CHECKING
from qgis.core import QgsTask, QgsApplication
from PyQt5.QtWidgets import QMessageBox

if TYPE_CHECKING:
    from .analysis_dialog import AnalysisDialog

class Task(QgsTask):
    """Generic task class for executing functions asynchronously."""
    
    def __init__(self, dialog: 'AnalysisDialog', run_logic: Callable, description: str):
        super().__init__(description, QgsTask.CanCancel)
        self.dialog = dialog
        self.run_logic = run_logic
        self.error = None
        self.exception = None

    def run(self):
        """Execute the function in background."""
        try:
            self.dialog.log_message(f"Starting task: {self.description()}", "Threads")
            self.run_logic(self.dialog)
            self.dialog.log_message(f"Task completed: {self.description()}", "Threads")
            return True
        except Exception as e:
            self.exception = e
            self.error = str(e)
            self.dialog.log_message(f"Task failed: {self.error}", "Threads")
            return False

    def finished(self, result: bool):
        """Handle task completion."""
        if result:
            self.dialog.log_message(f"Task completed successfully: {self.description()}", "Threads")
        else:
            error_msg = f"Task failed: {self.error}" if self.error else "Task failed with unknown error"
            self.dialog.log_message(error_msg, "Threads")
            QMessageBox.critical(self.dialog, "Error", error_msg)

def run_in_background(dialog: 'AnalysisDialog', run_logic: Callable):
    """Run a function as a background task with proper logging."""
    try:
        # Get a more readable name for the task
        name = run_logic.__name__.replace('_', ' ').title()
        
        # Create and configure the task
        task = Task(dialog, run_logic, f"Running {name}")
        
        # Add task to QGIS task manager
        QgsApplication.taskManager().addTask(task)
        
        # Log that we've started the task
        dialog.log_message(f"Added task to queue: {name}", "Threads")
        
    except Exception as e:
        error_msg = f"Failed to start task: {str(e)}"
        dialog.log_message(error_msg, "Threads")
        QMessageBox.critical(dialog, "Error", error_msg)
