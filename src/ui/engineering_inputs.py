"""Shared reader for the physics/cost inputs (the ``eng`` dict).

The engineering parameters (friction factor, CO₂ density, pressure budget, standardized cost factor,
booster costs) live as widgets on the Price Estimation tab, but the same physics drives two things that
must agree: the CAPEX estimate **and** the Level-3 MILP pipe sizing. Both read the values here so there
is a single source of truth. The widgets are created when the dialog is built and pre-populated with the
COMET reference values, so this is safe to call even if the user never opened the Price Estimation tab.

Qt lives on the caller side (this reads widgets); float parsing raises ``ValueError`` on bad input, which
the 3-phase task contract surfaces to the user.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..analysis_dialog import AnalysisDialog


def read_engineering_inputs(dialog: "AnalysisDialog") -> dict:
    """Read the engineering/cost inputs into the ``eng`` dict shared by CAPEX and the MILP.

    ``M`` (single-pipeline design mass flow) is included for the CAPEX single-mode path; the MILP ignores
    it and derives each pipe's flow from the network instead.

    :raises ValueError: if a field is non-numeric or the admissible pressure drop is not positive.
    """
    admissible_MPa_km = float(dialog.pressureDropInput.text())  # Δp/L, MPa/km
    if admissible_MPa_km <= 0:
        raise ValueError("Admissible Pressure Drop must be greater than zero.")
    return {
        "λ": float(dialog.frictionFactorInput.text()),
        "M": float(dialog.co2MassFlowRateInput.text()),
        "p": float(dialog.co2densityInput.text()),
        "Δp_Ltotal": admissible_MPa_km * 1000,  # MPa/km → Pa/m (pressure drop per meter)
        "total_pressure_drop": float(dialog.totalPressureDropInput.text()),  # MPa (max drop per segment)
        "admissible_MPa_km": admissible_MPa_km,
        "Bc": float(dialog.standardizedCostFactorInput.text()),
        "Beff": float(dialog.boosterEfficiencyInput.text()),
        "α": float(dialog.boosterVariableCostInput.text()),  # M€/MW (COMET default: capex.BOOSTER_VARIABLE_COST)
        "β": float(dialog.boosterFixedCostInput.text()),  # M€ fixed cost (COMET default: capex.BOOSTER_FIXED_COST)
    }
