"""Raster symbology helpers."""

from qgis.core import QgsRasterLayer


def apply_symbology(original_layer: QgsRasterLayer, clipped_layer: QgsRasterLayer):
    """Applies symbology from the original raster to the clipped raster."""
    if not original_layer or not clipped_layer:
        raise ValueError("Original layer or clipped layer is missing.")

    if not original_layer.isValid() or not clipped_layer.isValid():
        raise ValueError("One or both layers are invalid.")

    # Get the renderer from the original layer
    renderer = original_layer.renderer()
    if renderer:
        # Clone the renderer and apply to clipped layer
        clipped_layer.setRenderer(renderer.clone())
        clipped_layer.triggerRepaint()
    else:
        raise ValueError("Original layer has no renderer to copy.")
