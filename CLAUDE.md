# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A **QGIS plugin** (3.16+, including QGIS 4; PyQGIS with Qt via the `qgis.PyQt` wrapper) for CO₂ pipeline routing and CAPEX estimation. It implements the COMET multi-criteria cost model, raster least-cost-path routing via GRASS, and engineering-grade CAPEX estimation with a hydraulically-derived pipeline diameter. The plugin runs *inside* QGIS — there is no standalone entry point. See `README.md` for the full cost model, formulas, parameters, and the Portuguese case study.

The repo lives directly in the QGIS plugins directory (this checkout *is* the installed plugin), so edits take effect on the next QGIS restart / plugin reload — no deploy step needed during development.

## Issues & pull requests

This is an open-source repo. Follow the `/commit` skill for commit messages (Conventional
Commits; issues referenced in the scope and/or a `Closes #N` footer; no LLM co-author trailers).

When opening issues via `gh`, match the GitHub issue forms in `.github/ISSUE_TEMPLATE/`
(`bug_report.yml`, `feature_request.yml`, `change_request.yml`): use the same title prefix
(`[Bug]:` / `[Feature]:` / `[Improvement]:`) and fill the fields those forms ask for.

**Labels.** Two orthogonal axes plus a type label:

- `priority: low|medium|high` — how soon it should be addressed (scheduling). Applies to **every**
  issue (bugs, features, improvements).
- `severity: low|medium|high` — how bad the impact is if it occurs (technical impact). Applies to
  **bugs** only — it has no meaning for a feature request.
- A type label: `bug` / `enhancement` / `documentation`.

A bug can be high-severity but low-priority (rare edge case) or vice versa; set the two
independently. Example: the worker-thread bug is `severity: high` + `priority: high`; the lifecycle
cleanup is `severity: medium` + `priority: low`.

## Development workflow

- **No automated test suite exists.** The `make test` / `make pylint` targets in the `Makefile` assume the standard QGIS plugin-builder layout (a `*_dialog_base.ui`, `nosetests`) that this project does **not** use — they will not work as-is. Don't rely on them.
- **Lint:** `pylintrc` is present; run `pylint --rcfile=pylintrc <file>` inside a QGIS-aware Python env. PyQGIS imports (`qgis.core`, `qgis.processing`) only resolve against the QGIS-bundled interpreter (see `.vscode/settings.json` for the macOS interpreter path).
- **Manual testing** is the norm: reload the plugin in QGIS and exercise the dialog. The plugin logs verbosely to its in-dialog log panel (and a pop-out window) via `dialog.log_message(msg, tab_name)` — use this liberally for diagnostics rather than `print`.
- **Hard requirement:** the GRASS provider must be enabled in QGIS — routing calls `processing.run("grass7:r.cost")` / `r.drain`.

## Architecture

Entry point is `__init__.py` → `classFactory` → `LeastCostPipelinePlugin`, which adds one toolbar/menu action that opens `AnalysisDialog` (`src/analysis_dialog.py`). Everything happens in that single dialog.

**The dialog is a god-object passed everywhere.** `AnalysisDialog.__init__` declares every widget as a typed attribute (for IDE hinting), then `setup_ui` (`src/ui_manager.py`) builds a 7-tab `QTabWidget` and the bottom log panel. Each tab lives in `src/tabs/<name>_tab.py` and exposes the same module-level function pattern — **not classes**:

- `setup_<tab>_tab(dialog, layout)` — builds the widgets, assigns them onto `dialog` (e.g. `dialog.combineLandUseDropdown = QComboBox()`).
- `connect_<tab>_signals(dialog)` — wires buttons to handlers.
- `run_<action>(dialog)` — the actual work, reading inputs off `dialog` and logging to it.

So `dialog` is the shared bus for both widgets and the logger. When adding a widget, declare it in `analysis_dialog.py`, create it in the tab's `setup_`, and (if it's a layer dropdown) register it in `populate_layer_dropdowns` and `_make_all_dropdowns_searchable`.

**The 7 tabs form a sequential pipeline**, each producing an output consumed by the next: Land Use → Slope → Crossings → Corridors → Aux (helpers: merge/resample/clip) → LCP → Price Estimation. The four cost tabs each produce a cost-factor raster; LCP combines them and routes; Price Estimation re-applies the same factors along the route. See the README "Usage" table for inputs/outputs per tab.

**Long-running work runs off the UI thread** via `src/task_manager.py`: handlers call `run_in_background(dialog, run_logic)`, which wraps `run_logic` in a `QgsTask`. Consequences:
- `run_logic` must be self-contained and read everything it needs off `dialog`.
- Never touch widgets directly from inside a task — `dialog.log_message` is deliberately thread-safe (`QMetaObject.invokeMethod` + `QueuedConnection`); follow that pattern for any other cross-thread UI update.
- `_running_tasks` dedupes by function name, so re-clicking a button while it runs is a no-op.

**`src/utils.py`** holds the shared helpers: `populate_layer_dropdowns` (re-runs on `layersAdded`), `make_searchable_dropdown`, `get_layer_path`, `select_output_file`, resolution/length field updaters, symbology copy.

## Domain logic — where the math lives

Two places implement the COMET formula `Fc · Fs · [Flu·(1−0.1N) + 0.1N·Fci]`, and they **must stay consistent** — the routing surface and the cost estimate have to agree, otherwise the least-cost route is no longer the cheapest to build:

- **Routing surface:** `combine_rasters_with_comet_formula` in `src/tabs/lcp_tab.py` — resamples all rasters to a common extent/resolution with `gdal:warpreproject`, applies the formula as NumPy arrays, caps `N` at 10, floors output at 0.001 (so `r.drain` works). The LCP itself is the GRASS chain `r.cost` (accumulate from origin) → `r.drain` (back-trace from destination) → thin/vectorize, in `run_r_cost` / `run_r_drain_and_vectorize`.
- **CAPEX:** `run_price_estimation` in `src/tabs/price_estimation_tab.py` — computes diameter `D` once from Darcy-Weisbach, walks the route cell-by-cell, splits into segments by a pressure budget (`max_segment_length = total_pressure_drop / admissible_pressure_drop`), inserts booster stations between segments. Two sampling backends behind a radio button: `extract_raster_values_along_pipeline_cells` (precise, exact cell intersection) vs `extract_raster_values_along_pipeline` (fast, 5 sample points/segment, takes the max).

Missing cost rasters default to a neutral `1.0` in both paths. Greek/symbol identifiers (`λ`, `ρ`, `Δp`) are used intentionally to match the paper — preserve them.

Each cost tab has a **"Populate according to COMET"** button that fills its table with the reference values from the README. If you change a default cost factor, update both the populate handler and the README cost-model tables.
