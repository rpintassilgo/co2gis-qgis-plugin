"""Cross-cutting glue helpers, grouped by topic.

This package replaces the former monolithic ``utils.py``. The submodules hold the
implementations; the public names are re-exported here so existing
``from ..utils import X`` / ``from .utils import X`` imports keep working.
"""

from .dropdowns import make_searchable_dropdown
from .fields import update_pipeline_length, update_resolution_field
from .io import select_output_file, select_output_folder
from .layers import DROPDOWN_REGISTRY, get_layer_path, layer_from_dropdown, populate_layer_dropdowns
from .symbology import apply_symbology

__all__ = [
    "DROPDOWN_REGISTRY",
    "apply_symbology",
    "get_layer_path",
    "layer_from_dropdown",
    "make_searchable_dropdown",
    "populate_layer_dropdowns",
    "select_output_file",
    "select_output_folder",
    "update_pipeline_length",
    "update_resolution_field",
]
