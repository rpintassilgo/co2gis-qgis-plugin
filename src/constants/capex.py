"""CAPEX / hydraulic default values from the COMET reference project.

These seed the (user-editable) inputs in the Price Estimation tab. Defining them
here keeps the reference defaults in one place instead of as UI string literals.
"""

# Segment cost (Ip = Bc · D · Σ(Ccell · Lcell)).
STANDARDIZED_COST_FACTOR = 1357  # Bc

# Pipe diameter via Darcy-Weisbach: D = (8λM² / π²ρ(Δp/L))^(1/5).
FRICTION_FACTOR = 0.015  # λ
CO2_DENSITY = 827  # ρ, kg/m³

# Booster stations: Ib = (α · Sc[MW] + β) × 10⁶.
BOOSTER_EFFICIENCY = 0.75  # Beff
BOOSTER_VARIABLE_COST = 0.547  # α, M€/MW
BOOSTER_FIXED_COST = 0.42  # β, M€
