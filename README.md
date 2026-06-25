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

## Cost model & parameters

**Cost factors** (COMET, onshore):

| Factor | Category | Value |
|--------|----------|-------|
| `Flu` land use | unpopulated / cultivated / flooded / forest / urban / water | 1.0 / 1.1 / 1.2 / 1.3 / 1.8 / 4.0 |
| `Fs` slope | <10% / 10–20% / 20–30% / 30–70% / >70% | 1.0 / 1.1 / 1.2 / 3.0 / 9.0 |
| `Fci` crossing | none / road or rail | 1.0 / 3.0 |
| `Fc` corridor | existing / new (onshore) | 0.9 / 1.0 |

A cell cost ranges from ~**0.9** (existing corridor, easy terrain) to **36** (water on a steep slope).

**Physical & economic parameters:**

| Symbol | Description | Value |
|--------|-------------|-------|
| `Bc` | standardised cost factor | 1357 €₂₀₁₀/m² |
| `λ` | Darcy friction factor | 0.015 |
| `ρ` | CO₂ density (supercritical) | 827 kg/m³ |
| `Δp/L` | admissible pressure drop | 0.02 MPa/km |
| `L_max` | max segment length (booster spacing) | 150 km |
| `B_eff` | compressor efficiency | 0.75 |

### Precise vs fast

Fast mode replaces exact cell-by-cell intersection with five sample points per segment (taking the max — a conservative choice). On the most demanding scenario (Sagres–Bragança, 619 km):

| Configuration | Time | CAPEX deviation |
|---------------|------|-----------------|
| Native 10 m + precise (baseline) | ~73 min | — |
| Resampled 50 m + precise | ~7.5 min | 0.4% |
| **Resampled 50 m + fast** | **~2.2 min** | **3.9%** |

Resampling to 50 m alone cuts routing time by **~97%**. Use fast mode for exploration and sensitivity sweeps; precise mode for final estimates.

---

## Validation

CAPEX was checked against four operational CO₂ pipelines. Modelled unit costs (0.38–1.26 M€₂₀₁₀/km) fall within the real-world range (0.12–1.48 M€/km).

| Pipeline / scenario | Length (km) | Flow (kg/s) | CAPEX (M€₂₀₁₀) | M€/km |
|---------------------|------------:|------------:|---------------:|------:|
| Cortez (real) | 808 | 761 | 1193 | 1.48 |
| Weyburn (real) | 330 | 63 | 39 | 0.12 |
| Quest (real) | 84 | 38 | 100 | 1.19 |
| Qinshui (real) | 116 | 16 | 32 | 0.28 |
| **C4** Sagres–Bragança | 619 | 761 | 778 | 1.26 |
| **C3** Sines–Leiria | 237 | 63 | 110 | 0.46 |
| **C1** Leiria–Coimbra | 60 | 38 | 23 | 0.38 |

The bundled Portuguese case study runs entirely on open data: land use (COSc 2024, DGT), slope (SRTM-DEM), roads & railways (Infraestruturas de Portugal) and existing corridors (SRUP, DGT).

---

## Scope & limitations

- Cost factors come from **expert elicitation** (COMET stakeholders), not observed construction costs — a limitation shared by all CO₂ pipeline cost models.
- **CAPEX only** — no OPEX, social or environmental costs.
- **Point-to-point** routing; multi-source / multi-sink network optimisation is a planned extension.

---

## Contributing

Issues and pull requests are welcome. Use the [issue templates](https://github.com/rpintassilgo/co2gis-qgis-plugin/issues/new/choose) for bugs, feature requests and improvements. For commercial CCUS work needing custom development or priority support, reach out at **co2gis.support@gmail.com**.

---

## Acknowledgments

CO2GIS began as the practical component of a Master's dissertation in Computer Engineering at the **[Polytechnic University of Leiria](https://www.ipleiria.pt/)** (ESTG), in collaboration with the **[Net4CO2](https://net4co2.pt)** laboratory — and is now developed independently and in the open.

It builds on open-source foundations — **QGIS** and **GRASS GIS** — the **COMET** cost model ([Van den Broek et al., 2013](https://doi.org/10.1016/j.egypro.2013.06.200)) and the CCS Roadmap for Portugal (Seixas et al., 2015).

## Citation

```bibtex
@mastersthesis{pintassilgo2026co2gis,
  title  = {Plugin QGIS para Otimiza\c{c}\~ao do Tra\c{c}ado e do Investimento para Gasodutos de CO2},
  author = {Pintassilgo, Rodrigo},
  school = {Escola Superior de Tecnologia e Gest\~ao, Polit\'ecnico de Leiria},
  year   = {2026}
}
```

## License

**GNU General Public License v2.0 or later** ([GPL-2.0-or-later](LICENSE)), consistent with QGIS and GRASS GIS.
