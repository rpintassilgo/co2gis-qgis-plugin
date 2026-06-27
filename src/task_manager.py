"""Background-task runner.

Tasks use the 3-phase contract via :func:`run_task` (prepare / work / publish):
``prepare`` and ``publish`` run on the **main thread**; only ``work`` runs on the
background thread and must not touch Qt widgets or ``QgsProject`` (#2).

Errors are never swallowed: a failing ``work``/``publish`` marks the task failed,
logs it and shows a QMessageBox (fixes the false-success bug, #7).
"""

from typing import TYPE_CHECKING, Callable, Optional

from qgis.core import QgsApplication, QgsTask
from qgis.PyQt.QtWidgets import QMessageBox

if TYPE_CHECKING:
    from .analysis_dialog import AnalysisDialog


class Task(QgsTask):
    """Runs ``work(params)`` off the UI thread, then ``publish`` on the main thread."""

    def __init__(self, dialog: "AnalysisDialog", name: str, work: Callable, params, publish: Optional[Callable]):
        super().__init__(f"Running {name}", QgsTask.CanCancel)
        self.dialog = dialog
        self.name = name
        self._work = work
        self._params = params
        self._publish = publish
        self.result = None
        self.error = None
        self.exception = None

    def run(self):
        """Background thread: pure work only (no widgets, no QgsProject)."""
        try:
            self.result = self._work(self._params)
            return True
        except Exception as e:
            self.exception = e
            self.error = str(e)
            return False

    def finished(self, ok):
        """Main thread: publish results on success, surface errors on failure."""
        if not ok:
            msg = self.error or "unknown error"
            self.dialog.log_message(f"Task '{self.name}' failed: {msg}", "Task Manager")
            QMessageBox.critical(self.dialog, "Error", f"{self.name} failed:\n{msg}")
            return

        try:
            if self._publish is not None:
                self._publish(self.dialog, self.result)
        except Exception as e:
            self.dialog.log_message(f"Task '{self.name}' failed while loading results: {e}", "Task Manager")
            QMessageBox.critical(self.dialog, "Error", f"{self.name} failed while loading results:\n{e}")
            return

        self.dialog.log_message(f"Task '{self.name}' completed successfully", "Task Manager")

    def cancel(self):
        self.dialog.log_message(f"Task '{self.name}' was cancelled", "Task Manager")
        super().cancel()


# Keep track of running tasks to prevent duplicates (keyed by action name + dialog).
_running_tasks = {}


def _is_running(task_key: str) -> bool:
    existing = _running_tasks.get(task_key)
    if existing is not None and existing.status() in (QgsTask.Running, QgsTask.Queued):
        return True
    _running_tasks.pop(task_key, None)
    return False


def _schedule(dialog: "AnalysisDialog", name: str, task: "Task", task_key: str):
    _running_tasks[task_key] = task

    def cleanup():
        _running_tasks.pop(task_key, None)

    task.taskCompleted.connect(cleanup)
    task.taskTerminated.connect(cleanup)
    QgsApplication.taskManager().addTask(task)
    dialog.log_message(f"Started task: {name}", "Task Manager")


def run_task(
    dialog: "AnalysisDialog",
    name: str,
    work: Callable,
    *,
    prepare: Optional[Callable] = None,
    publish: Optional[Callable] = None,
):
    """Run an action under the 3-phase contract.

    :param name: human-readable action name (used for dedup + logging).
    :param prepare: ``prepare(dialog) -> params`` on the main thread — read widgets,
        resolve selected layers to source paths, validate (raise ``ValueError`` on
        bad input). Its return value is passed to ``work``.
    :param work: ``work(params) -> result`` on the background thread — pure
        computation (NumPy / GDAL / processing on captured paths/values); no Qt,
        no ``QgsProject``. Returns a result for ``publish``.
    :param publish: ``publish(dialog, result)`` on the main thread — load output
        layers into the project, apply symbology, etc.
    """
    task_key = f"{name}_{id(dialog)}"
    if _is_running(task_key):
        dialog.log_message(f"Task '{name}' is already running", "Task Manager")
        return

    # prepare runs now, on the main thread.
    try:
        params = prepare(dialog) if prepare is not None else None
    except Exception as e:
        dialog.log_message(f"{name} failed: {e}", "Task Manager")
        QMessageBox.critical(dialog, "Error", f"{name} failed:\n{e}")
        return

    _schedule(dialog, name, Task(dialog, name, work, params, publish), task_key)
