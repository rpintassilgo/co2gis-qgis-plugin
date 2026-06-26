"""COMET land-use cost defaults.

Maps land-use class IDs from the Portuguese "Carta de Ocupação do Solo
Conjuntural" (Direção-Geral do Território) to their COMET cost factor (Flu).
Used by the Land Use tab's "Populate according to COMET" button.
"""

# class_id -> cost factor (Flu)
COMET_LAND_USE_COSTS = {
    100: 1.8,
    211: 1.1,
    212: 1.1,
    213: 1.1,
    311: 1.3,
    312: 1.3,
    313: 1.3,
    321: 1.3,
    322: 1.3,
    323: 1.3,
    410: 1.1,
    420: 1.1,
    500: 1.0,
    610: 1.2,
    620: 4.0,
}
