from typing import Callable, TYPE_CHECKING
from qgis.core import QgsTask, QgsApplication
from PyQt5.QtWidgets import QMessageBox

if TYPE_CHECKING:
    from .analysis_dialog import AnalysisDialog

class Task(QgsTask):
    """Generic task class for executing functions asynchronously."""
    
    def __init__(self, dialog: 'AnalysisDialog', run_logic: Callable, description: str):
        super().__init__(description, QgsTask.CanCancel)
        self.dialog: 'AnalysisDialog' = dialog
        self.run_logic = run_logic
        self.error = None
        self.exception = None

    def run(self):
        """Execute the function in background."""
        try:
            self.run_logic(self.dialog)
            return True
        except Exception as e:
            self.exception = e
            self.error = str(e)
            return False

    def finished(self, result):
        """Called when the task is complete."""
        if result:
            self.dialog.log_message(f"Task '{self.description()}' completed successfully", "Task Manager")
        elif self.error:
            self.dialog.log_message(f"Task '{self.description()}' failed: {self.error}", "Task Manager")
            QMessageBox.critical(self.dialog, "Error", f"Task failed: {self.error}")

    def cancel(self):
        """Called when the task is cancelled."""
        self.dialog.log_message(f"Task '{self.description()}' was cancelled", "Task Manager")
        super().cancel()

# Keep track of running tasks to prevent duplicates
_running_tasks = {}

def run_in_background(dialog: 'AnalysisDialog', run_logic: Callable):
    """Run a function as a background task with proper logging."""
    try:
        # Get a more readable name for the task
        name = run_logic.__name__.replace('_', ' ').title()
        
        # Check if this task is already running
        task_key = f"{name}_{id(dialog)}"
        if task_key in _running_tasks:
            existing_task = _running_tasks[task_key]
            if not existing_task.isFinished():
                dialog.log_message(f"Task '{name}' is already running", "Task Manager")
                return
            else:
                # Clean up finished task
                del _running_tasks[task_key]
        
        # Create and configure the task
        task = Task(dialog, run_logic, f"Running {name}")
        
        # Store the task reference
        _running_tasks[task_key] = task
        
        # Add cleanup on completion - no result parameter needed
        def cleanup():
            if task_key in _running_tasks:
                del _running_tasks[task_key]
        
        task.taskCompleted.connect(cleanup)
        task.taskTerminated.connect(cleanup)
        
        # Add the task to QGIS task manager
        QgsApplication.taskManager().addTask(task)
        dialog.log_message(f"Started task: {name}", "Task Manager")
        
    except Exception as e:
        error_msg = f"Failed to start task: {str(e)}"
        dialog.log_message(error_msg, "Task Manager")
        QMessageBox.critical(dialog, "Error", error_msg)
