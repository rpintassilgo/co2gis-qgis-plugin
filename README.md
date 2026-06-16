# LeastCostPipeline

**A QGIS plugin for optimised CO₂ pipeline routing and CAPEX estimation.**

![QGIS](https://img.shields.io/badge/QGIS-3.0%2B-589632?logo=qgis&logoColor=white)
![License](https://img.shields.io/badge/license-GPL--2.0--or--later-blue)
![Version](https://img.shields.io/badge/version-1.0.0-informational)

LeastCostPipeline combines **raster-based least-cost path (LCP) routing** with **cell-level capital-cost (CAPEX) estimation** for planning CO₂ transport pipelines, in a single interactive QGIS interface — no programming required. It implements the [COMET multi-criteria cost model (Van den Broek et al., 2013)](https://doi.org/10.1016/j.egypro.2013.06.200), least-cost path computation via GRASS GIS, and CAPEX estimation with a hydraulically-derived pipeline diameter.

> Developed as the practical component of a Master's dissertation in Computer Engineering – Mobile Computing (ESTG / Polytechnic of Leiria), in collaboration with the **Net4CO2** collaborative laboratory.

---

## Why this tool

Designing a CO₂ pipeline route is a multi-criteria spatial problem: the best corridor depends on land use, terrain slope, infrastructure crossings and existing corridors, while the total cost depends on length, diameter and pressure. These factors interact across a whole country, so manual approaches are impractical.

Existing tools treat the two halves separately. General-purpose GIS offers LCP but no CO₂-specific cost model; [SimCCS](https://doi.org/10.1016/j.envsoft.2019.104560) optimises **networks** on a weighted **graph** model rather than continuous raster surfaces, and does not estimate CAPEX at the cell level. To the best of our knowledge, **no other tool combines a COMET raster cost surface, raster LCP routing and engineering-grade cell-level CAPEX in one accessible GIS workflow** — and none is adapted to Portugal. That is the gap this plugin fills.

---

## Features

- **Multi-criteria cost surface** from four territorial factors: land use, slope, infrastructure crossings, existing corridors.
- **Least-cost path routing** using the GRASS GIS algorithm chain (`r.cost → r.drain → r.thin → r.to.vect`).
- **CAPEX estimation** following the COMET cost model, with pipeline **diameter derived from the Darcy-Weisbach equation** and **booster stations** inserted on segments longer than 150 km.
- **Two estimation modes** — a *precise* cell-by-cell mode and a *fast* point-sampling mode — giving a user-controlled accuracy/speed trade-off.
- **No coding required** — a tabbed interface that walks the user through the whole workflow, with COMET reference values one click away.
- **Open data, reproducible** — fully parameterisable; ships with a Portuguese case study built entirely on open datasets.

---

## How it works

The plugin follows three sequential steps.

### 1 · Cost surface

Each raster cell is assigned a relative crossing cost using the COMET formula:

```
C_cell = Fc · Fs · [ Flu · (1 − 0.1·N) + 0.1·N · Fci ]
```

where `Fc` = existing-corridor factor, `Fs` = slope factor, `Flu` = land-use factor, `Fci` = crossing factor, and `N` = number of road/rail features intersecting the cell (capped at 10). The bracket is a weighted average between land use (`N = 0`) and crossing cost (`N = 10`).

### 2 · Least-cost path

The optimal route minimises the **accumulated** cell cost from origin to destination. `r.cost` propagates the accumulated cost from the origin; `r.drain` back-traces the minimum-cost path from the destination; `r.thin` + `r.to.vect` turn it into a clean line geometry. The result is the **globally optimal** corridor, not a greedy local path.

### 3 · CAPEX estimation

The pipeline diameter is computed once from the CO₂ mass flow rate via Darcy-Weisbach:

```
D = ( 8·λ·M² / (π²·ρ·(Δp/L)) )^(1/5)
```

The segment cost reuses the **same cost factors** from the routing surface — so the least-cost route is, by construction, also the cheapest to build:

```
Ip      = Bc · D · Σ ( C_cell · L_cell )
I_total = Σ Ip + Σ I_B
```

Routes over 150 km (the hydraulic limit at Δp/L = 0.02 MPa/km and 3 MPa max drop) are split into segments with intermediate **booster stations**, whose cost `I_B = 0.547·Sc + 0.42` (M€₂₀₁₀) scales with compressor power.

---

## Installation

**Requirements:** QGIS **3.0 or newer**, with the bundled **GRASS provider** and **Processing** framework (included in the standard QGIS installers). No extra Python packages are needed — the plugin uses only PyQGIS, PyQt5, GDAL/OGR and NumPy, all shipped with QGIS.

**From ZIP (recommended):**
1. Download this repository as a ZIP (or a packaged release).
2. In QGIS: **Plugins → Manage and Install Plugins → Install from ZIP**.
3. Enable **LeastCostPipeline** in the *Installed* tab.

**Manual:** copy the `least_cost_pipeline` folder into your QGIS plugins directory and restart QGIS:
- **Linux:** `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
- **macOS:** `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
- **Windows:** `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`

A **Least Cost Pipeline** action then appears in the Plugins menu and toolbar.

---

## Usage

The interface is organised as a workflow of seven tabs. Each tab produces an output used by the next.

| Tab | Input | Output |
|-----|-------|--------|
| **Land Use** | classified land-cover raster (e.g. COSc) | `Flu` cost raster |
| **Slope** | DEM | slope raster → `Fs` cost raster |
| **Crossings** | road/rail vector | `Fci` cost raster + `N` count raster |
| **Corridors** | existing pipeline/oil corridors vector | `Fc` cost raster (with water-body / onshore–offshore handling) |
| **Aux** | — | merge vectors, resample and clip rasters (speed-ups) |
| **LCP** | the four cost rasters + `N` + origin/destination points | combined cost raster → **route (vector)** |
| **Price Estimation** | route + cost rasters + flow/physical parameters | **CAPEX** (precise or fast mode) |

Each cost tab has a **Populate according to COMET** button that fills in the reference values automatically. Every parameter is editable.

---

## Cost model & parameters

**Cost factors** (COMET, onshore):

| Factor | Category | Value |
|--------|----------|-------|
| `Flu` land use | unpopulated | 1.0 |
| | cultivated / arid | 1.1 |
| | regularly flooded | 1.2 |
| | forest | 1.3 |
| | urban | 1.8 |
| | water bodies | 4.0 |
| `Fs` slope | <10% / 10–20% / 20–30% / 30–70% / >70% | 1.0 / 1.1 / 1.2 / 3.0 / 9.0 |
| `Fci` crossing | none / road or rail | 1.0 / 3.0 |
| `Fc` corridor | existing (onshore) / new (onshore) | 0.9 / 1.0 |

Combined, a cell cost ranges from ~**0.9** (existing corridor on easy terrain) to **36** (water on a steep slope).

**Physical & economic parameters:**

| Symbol | Description | Value |
|--------|-------------|-------|
| `Bc` | standardised cost factor | 1357 €₂₀₁₀/m² |
| `λ` | Darcy friction factor | 0.015 |
| `ρ` | CO₂ density (supercritical) | 827 kg/m³ |
| `Δp/L` | admissible pressure drop | 0.02 MPa/km |
| `L_max` | max segment length (booster spacing) | 150 km |
| `B_eff` | compressor efficiency | 0.75 |

---

## Two estimation modes

The fast mode replaces exact cell-by-cell geometric intersection with five sample points per segment (taking the maximum, a conservative choice). On the most demanding scenario (Sagres–Bragança, 619 km):

| Configuration | Total time | CAPEX deviation |
|---------------|-----------|-----------------|
| Native 10 m + precise (baseline) | ~73 min | — |
| Full-50 m + precise | ~7.5 min | 0.4% |
| **Full-50 m + fast** | **~2.2 min** | **3.9%** |

Resampling to 50 m alone cuts LCP time by **97%** (25× fewer cells). The fast mode is suited to scenario exploration and sensitivity analysis; precise mode to final estimates.

---

## Data sources (Portuguese case study)

All open datasets:

- **Land use** — Carta de Ocupação do Solo Conjuntural (COSc) 2024, 10 m (Direção-Geral do Território).
- **Slope** — SRTM-DEM, 25 m, reprojected to EPSG:3763 (via FCUP).
- **Roads & railways** — Rede rodoviária / ferroviária nacional (Infraestruturas de Portugal).
- **Existing corridors** — SRUP gas/oil pipelines, WFS (Direção-Geral do Território).

---

## Validation

CAPEX estimates were validated against four operational CO₂ pipelines. Model estimates (unit cost 0.38–1.26 M€₂₀₁₀/km) fall within the real-world range (0.12–1.48 M€/km).

| Pipeline / scenario | Length (km) | Flow (kg/s) | CAPEX (M€₂₀₁₀) | M€/km |
|---------------------|-------------|-------------|----------------|-------|
| Cortez (real) | 808 | 761 | 1193 | 1.48 |
| Weyburn (real) | 330 | 63 | 39 | 0.12 |
| Quest (real) | 84 | 38 | 100 | 1.19 |
| Qinshui (real) | 116 | 16 | 32 | 0.28 |
| **C4** Sagres–Bragança | 619 | 761 | 778 | 1.26 |
| **C3** Sines–Leiria | 237 | 63 | 110 | 0.46 |
| **C2** Sines–Leiria | 237 | 38 | 90 | 0.38 |
| **C1** Leiria–Coimbra | 60 | 38 | 23 | 0.38 |

---

## Screenshots

> Add the figures from the paper to `docs/` (`docs/plugin-interface.png`, `docs/example-route.png`).

| Plugin interface | Example route |
|---|---|
| ![Plugin interface](docs/plugin-interface.png) | ![Example route](docs/example-route.png) |

---

## Limitations & future work

- Cost factors come from **expert elicitation** (COMET stakeholders), not observed construction costs — a limitation shared by all CO₂ pipeline cost models.
- **CAPEX only** — no OPEX, social or environmental costs.
- No **sensitivity analysis** over the COMET factors yet (the plugin exposes every parameter, but the systematic study is future work).
- **Point-to-point** routing only — multi-source / multi-sink network optimisation is a planned extension.

---

## Citation

If you use this tool, please cite the dissertation (and the paper, once published):

> Pintassilgo, R. (2026). *Plugin QGIS para Otimização do Traçado e do Investimento para Gasodutos de CO₂* [Master's dissertation, Escola Superior de Tecnologia e Gestão, Politécnico de Leiria].

> Pintassilgo, R. (2026). *A QGIS Plugin for Optimised CO₂ Pipeline Routing and CAPEX Estimation: An Accuracy-Efficiency Analysis.*

```bibtex
@mastersthesis{pintassilgo2026leastcostpipeline,
  title  = {Plugin QGIS para Otimiza\c{c}\~ao do Tra\c{c}ado e do Investimento para Gasodutos de CO2},
  author = {Pintassilgo, Rodrigo},
  school = {Escola Superior de Tecnologia e Gest\~ao, Polit\'ecnico de Leiria},
  year   = {2026}
}
```

---

## Author & acknowledgements

Developed by **Rodrigo Pintassilgo** (MEI – Mobile Computing, ESTG / Polytechnic of Leiria).

This work was carried out in collaboration with the **[Net4CO2](https://net4co2.pt)** collaborative laboratory, and builds on the COMET model of Van den Broek et al. (2013) and the CCS Roadmap for Portugal (Seixas et al., 2015).

---

## License

Released under the **GNU General Public License v2.0 or later (GPL-2.0-or-later)**, consistent with QGIS and GRASS GIS. See [`LICENSE`](LICENSE).
