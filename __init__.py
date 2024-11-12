# -*- coding: utf-8 -*-
"""
/***************************************************************************
 LeastCostPipeline
                                  A QGIS plugin
 Calculate least cost co2 pipeline
 ***************************************************************************/
"""

from .least_cost_pipeline import LeastCostPipelinePlugin

def classFactory(iface):
    """Load LeastCostPipelinePlugin class."""
    return LeastCostPipelinePlugin(iface)
