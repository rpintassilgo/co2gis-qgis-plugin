# CO2GIS

**Route CO₂ pipelines the least-cost way — and price them — inside QGIS.**

![QGIS](https://img.shields.io/badge/QGIS-3.0%2B-589632?logo=qgis&logoColor=white)
![License](https://img.shields.io/badge/license-GPL--2.0--or--later-blue)

CO2GIS turns land use, slope, crossings and existing corridors into a [COMET](https://doi.org/10.1016/j.egypro.2013.06.200) cost surface, finds the globally optimal corridor between a source and a sink, and estimates its CAPEX down to the cell — all in one tabbed QGIS interface, no programming required.

▶ **[Watch the 2-minute demo](https://www.youtube.com/watch?v=j7pniEh9YSc)**

Planning a CO₂ pipeline is a multi-criteria spatial problem — the best corridor depends on land, terrain and infrastructure, while the cost depends on length, diameter and pressure. General GIS does routing but has no CO₂ cost model; network optimisers price graphs, not continuous terrain. CO2GIS joins a COMET raster cost surface, raster least-cost routing and engineering-grade cell-level CAPEX in a single workflow.

---

## Features

- **COMET cost surface** — land use, slope, infrastructure crossings and existing corridors combine into one relative crossing-cost per raster cell.
- **Globally optimal routing** — accumulated-cost path via the GRASS chain (`r.cost → r.drain → r.thin → r.to.vect`); the true least-cost corridor, not a greedy guess.
- **Cell-level CAPEX** — pipeline diameter from Darcy–Weisbach, priced from the *same* factors that drove the route, with booster stations inserted past the pressure budget.
- **Precise or fast** — exact cell-by-cell estimation, or a fast point-sampling mode for scenario exploration. You choose accuracy vs speed.
- **No coding** — a seven-tab workflow with COMET reference values one click away, every parameter editable.

---

## How it works

### 1 · Cost surface

Each raster cell gets a relative crossing cost from the COMET formula:

```
C_cell = Fc · Fs · [ Flu · (1 − 0.1·N) + 0.1·N · Fci ]
```

`Fc` = corridor factor, `Fs` = slope, `Flu` = land use, `Fci` = crossing, `N` = road/rail features in the cell (capped at 10). The bracket blends land-use cost (`N = 0`) and crossing cost (`N = 10`).

### 2 · Least-cost path

`r.cost` propagates accumulated cost from the origin; `r.drain` back-traces the minimum-cost path from the destination; `r.thin → r.to.vect` turn it into a clean line. The result is the route that minimises total accumulated cost across the whole territory.

### 3 · CAPEX

Diameter is computed once from the CO₂ mass flow rate via Darcy–Weisbach:

```
D = ( 8·λ·M² / (π²·ρ·(Δp/L)) )^(1/5)
```

The route is then priced cell by cell, reusing the routing factors — so the least-cost route is, by construction, also the cheapest to build:

```
Ip      = Bc · D · Σ ( C_cell · L_cell )
I_total = Σ Ip + Σ I_B
```

Runs past the hydraulic limit (≈150 km at Δp/L = 0.02 MPa/km, 3 MPa max drop) are split with intermediate **booster stations**, `I_B = 0.547·Sc + 0.42` (M€₂₀₁₀).

---

## Install

**From the QGIS Plugin Repository (recommended)** — in QGIS: **Plugins → Manage and Install Plugins**, search **CO2GIS**, install.

**From ZIP** — download a [release](https://github.com/rpintassilgo/co2gis-qgis-plugin/releases) and use **Plugins → Manage and Install Plugins → Install from ZIP**.

**Requirements:** QGIS **3.0+** with the bundled **GRASS provider** and **Processing** framework (both ship with the standard QGIS installers). No extra Python packages — the plugin uses only PyQGIS, PyQt5, GDAL/OGR and NumPy.

Once enabled, a **CO2GIS** action appears in the Plugins menu and toolbar.

---

## Usage

Seven tabs, each feeding the next:

| Tab | Input | Output |
|-----|-------|--------|
| **Land Use** | classified land-cover raster (e.g. COSc) | `Flu` cost raster |
| **Slope** | DEM | `Fs` cost raster |
| **Crossings** | road/rail vector | `Fci` cost raster + `N` count raster |
| **Corridors** | existing pipeline/oil corridors vector | `Fc` cost raster |
| **Aux** | — | merge vectors, resample & clip rasters (speed-ups) |
| **LCP** | the four cost rasters + `N` + origin/destination | combined cost raster → **route** |
| **Price Estimation** | route + cost rasters + flow/physical parameters | **CAPEX** (precise or fast) |

Each cost tab has a **Populate according to COMET** button that fills in reference values. Every parameter stays editable.

---

## Contributing

Issues and pull requests are welcome — see **[CONTRIBUTING.md](CONTRIBUTING.md)**.

---

## Acknowledgments

CO2GIS began as the practical component of a Master's dissertation in Computer Engineering at the **[Polytechnic University of Leiria](https://www.ipleiria.pt/)** (ESTG) — and is now developed independently and in the open.

## License

**GNU General Public License v2.0 or later** ([GPL-2.0-or-later](LICENSE)), consistent with QGIS and GRASS GIS.
