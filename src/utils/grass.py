"""GRASS processing helpers."""


def grass_alg_id(name: str) -> str:
    """
    Resolve a GRASS processing algorithm id across QGIS versions.

    QGIS 3.x registers GRASS algorithms under the ``grass7:`` prefix; QGIS 4.x
    renamed the provider to ``grass:``. Probe the processing registry and return
    whichever prefix is actually available, preferring the modern ``grass:``
    form and falling back to it when neither is found.

    :param name: algorithm name without prefix, e.g. ``"r.cost"``.
    """
    from qgis.core import QgsApplication

    registry = QgsApplication.processingRegistry()
    for prefix in ("grass", "grass7"):
        alg_id = f"{prefix}:{name}"
        if registry.algorithmById(alg_id) is not None:
            return alg_id
    return f"grass:{name}"
