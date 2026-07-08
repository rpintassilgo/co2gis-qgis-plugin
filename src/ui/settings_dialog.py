"""Global plugin settings — a small dialog opened from the header "⚙ Settings" button.

Currently exposes a single tunable: the RAM budget (in MB) handed to GRASS ``r.cost``
during least-cost-path routing. The value persists across QGIS restarts via ``QgsSettings``
and defaults to 8000 MB, matching the historically hardcoded value so behavior is unchanged
out of the box.
"""

from typing import TYPE_CHECKING

from qgis.core import QgsSettings
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

from ..constants.lcp import (
    DEFAULT_NETWORK_MODE_EXPERIMENTAL,
    DEFAULT_RCOST_MEMORY_MB,
    MAX_RCOST_MEMORY_MB,
    MIN_RCOST_MEMORY_MB,
    NETWORK_MODE_EXPERIMENTAL_KEY,
    RCOST_MEMORY_KEY,
    RCOST_MEMORY_STEP_MB,
)

if TYPE_CHECKING:
    from ..analysis_dialog import AnalysisDialog


def load_rcost_memory_mb() -> int:
    """Read the persisted r.cost memory budget (MB), falling back to the default."""
    return QgsSettings().value(RCOST_MEMORY_KEY, DEFAULT_RCOST_MEMORY_MB, type=int)


def save_rcost_memory_mb(value: int) -> None:
    """Persist the r.cost memory budget (MB) so it survives QGIS restarts."""
    QgsSettings().setValue(RCOST_MEMORY_KEY, int(value))


def load_network_mode_experimental() -> bool:
    """Read the persisted experimental Network-mode toggle, falling back to the default (off)."""
    return QgsSettings().value(NETWORK_MODE_EXPERIMENTAL_KEY, DEFAULT_NETWORK_MODE_EXPERIMENTAL, type=bool)


def save_network_mode_experimental(value: bool) -> None:
    """Persist the experimental Network-mode toggle so it survives QGIS restarts."""
    QgsSettings().setValue(NETWORK_MODE_EXPERIMENTAL_KEY, bool(value))


def open_settings_dialog(dialog: "AnalysisDialog") -> None:
    """Open the Settings dialog; on OK, persist the values and update the dialog state."""
    settings = SettingsDialog(dialog.rcost_memory_mb, dialog.network_mode_experimental, dialog)
    if settings.exec():
        value = settings.rcost_memory_mb()
        save_rcost_memory_mb(value)
        dialog.rcost_memory_mb = value
        dialog.log_message(f"GRASS r.cost memory budget set to {value} MB", "Settings")

        network_experimental = settings.network_mode_experimental()
        save_network_mode_experimental(network_experimental)
        dialog.network_mode_experimental = network_experimental
        state = "enabled" if network_experimental else "disabled"
        dialog.log_message(f"Experimental Network mode {state} (reload the plugin to apply)", "Settings")


class SettingsDialog(QDialog):
    """Modal dialog for global plugin settings."""

    def __init__(self, current_memory_mb: int, current_network_experimental: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(360)
        self.setSizeGripEnabled(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        form = QFormLayout()
        self._memory_spinbox = QSpinBox()
        self._memory_spinbox.setRange(MIN_RCOST_MEMORY_MB, MAX_RCOST_MEMORY_MB)
        self._memory_spinbox.setSingleStep(RCOST_MEMORY_STEP_MB)
        self._memory_spinbox.setSuffix(" MB")
        self._memory_spinbox.setValue(current_memory_mb)
        self._memory_spinbox.setToolTip(
            "RAM budget passed to GRASS r.cost during least-cost-path routing. "
            "Higher values speed up large rasters but must fit in available memory."
        )
        form.addRow(QLabel("GRASS r.cost memory:"), self._memory_spinbox)

        self._network_experimental_checkbox = QCheckBox()
        self._network_experimental_checkbox.setChecked(current_network_experimental)
        self._network_experimental_checkbox.setToolTip(
            "Work-in-progress N:M pipeline network mode. Off by default; enabling it reveals a "
            "Single/Network switch on the LCP tab after a plugin reload."
        )
        form.addRow(QLabel("Enable Network mode (experimental):"), self._network_experimental_checkbox)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def rcost_memory_mb(self) -> int:
        """Return the memory budget (MB) currently entered in the spinbox."""
        return self._memory_spinbox.value()

    def network_mode_experimental(self) -> bool:
        """Return whether the experimental Network-mode checkbox is currently ticked."""
        return self._network_experimental_checkbox.isChecked()
