"""Bridge between QGIS point layers and the pure network model.

Converts selected source/sink point layers into :class:`Node` objects — reading
the chosen attribute field (flow / injection rate) and reprojecting each point to
the routing CRS. Uses PyQGIS but never touches Qt widgets or the dialog, so it
belongs in ``core`` and is called from the tab's ``prepare`` phase (main thread).

The pure data model lives in ``model.py``; the GRASS routing that consumes these
nodes lives in ``routing.py``. This module is the natural home for the reverse
direction too (writing the network model back to a layer) as later levels need it.
"""

from __future__ import annotations

from qgis.core import QgsCoordinateTransform, QgsProject

from .model import Node


def build_nodes(layer, kind, value_field, value_name, target_crs, prefix, log=lambda msg: None):
    """Build :class:`Node` objects from a point layer, reprojected to ``target_crs``.

    :param layer: a point ``QgsVectorLayer`` (sources or sinks).
    :param kind: :data:`~src.core.networks.model.SOURCE` or ``SINK``.
    :param value_field: attribute field name holding the per-node value.
    :param value_name: the Node attribute to fill — ``"flow"`` or ``"capacity"``.
    :param target_crs: the routing CRS (the combined raster's CRS) to reproject to.
    :param prefix: id prefix so source/sink ids never collide (e.g. ``"S"`` / ``"K"``).
    :param log: optional progress callback.
    :returns: list of Nodes; a feature with a non-numeric/empty value gets 0 (logged).
    """
    xform = QgsCoordinateTransform(layer.crs(), target_crs, QgsProject.instance())
    nodes = []
    for feat in layer.getFeatures():
        geom = feat.geometry()
        if geom.isEmpty():
            continue
        pt = geom.asPoint() if not geom.isMultipart() else geom.asMultiPoint()[0]
        pt = xform.transform(pt)
        try:
            value = float(feat[value_field])
        except (TypeError, ValueError):
            value = 0.0
            log(f"  ⚠️ Feature {feat.id()} has no numeric {value_name}; using 0.")
        nodes.append(Node(id=f"{prefix}{feat.id()}", x=pt.x(), y=pt.y(), kind=kind, **{value_name: value}))
    return nodes
