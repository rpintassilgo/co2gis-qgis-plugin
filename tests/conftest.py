"""Shared pytest setup for the unit suite.

These tests exercise the *pure* domain math in ``src.core`` (COMET cell cost,
Darcy-Weisbach diameter, segment splitting / booster placement). Those functions
use only NumPy, but the modules that host them (``capex``, ``raster``) import
QGIS/GDAL at load time for their sampling helpers. We stub those runtime
dependencies here so the unit tests import and run with a plain
``python -m pytest`` — no QGIS installation, no display, no ``pytest-qgis``.

Integration tests that genuinely drive QGIS/GRASS belong under ``tests/qgis``
(see issue #10, phase 2) and must NOT rely on these stubs.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Repo root on sys.path so ``import src.core.<module>`` resolves (``src`` is an
# implicit namespace package; ``src/core`` and ``src/constants`` are packages).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Stand-ins for the QGIS/GDAL runtime. MagicMock auto-creates any attribute, so
# ``from qgis.core import QgsGeometry`` / ``from qgis import processing`` /
# ``from osgeo import gdal`` all succeed without the real packages installed.
_STUBBED_MODULES = (
    "qgis",
    "qgis.core",
    "qgis.gui",
    "qgis.utils",
    "processing",
    "osgeo",
    "osgeo.gdal",
    "osgeo.ogr",
)
for _name in _STUBBED_MODULES:
    sys.modules.setdefault(_name, MagicMock())
