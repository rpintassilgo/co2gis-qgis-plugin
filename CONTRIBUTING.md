# Contributing to CO2GIS

Thanks for considering a contribution! 🎉 These are guidelines, not hard rules — use your best judgment, and feel free to propose changes to this document in a pull request.

## Reporting bugs & requesting features

Open an issue through the [templates](https://github.com/rpintassilgo/co2gis-qgis-plugin/issues/new/choose):

- **🐛 Bug report** — what you did, what you expected, what happened. Include your QGIS version, OS, and any messages from the plugin's log panel.
- **✨ Feature request** — the problem you're trying to solve, not just the solution.
- **🛠 Improvement** — a change to existing behaviour, docs or UX.

Please search existing issues first to avoid duplicates.

## Development setup

CO2GIS is a QGIS 3.x plugin (PyQGIS / PyQt5) — there's no standalone entry point, it runs inside QGIS. The repository **is** the installed plugin, so it has to live in your QGIS plugins directory:

- **Linux:** `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
- **macOS:** `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
- **Windows:** `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`

[Fork](https://github.com/rpintassilgo/co2gis-qgis-plugin/fork) the repository, then clone your fork into that directory:

```bash
git clone https://github.com/<your-username>/co2gis-qgis-plugin.git
```

Then enable **CO2GIS** in *Plugins → Manage and Install Plugins → Installed*. Edits take effect on the next plugin reload — the [Plugin Reloader](https://plugins.qgis.org/plugins/plugin_reloader/) plugin is handy during development.

**Requirements:** QGIS 3.16+ with the **GRASS provider** enabled (routing calls `grass7:r.cost` / `r.drain`) and the Processing framework. No extra Python packages — only PyQGIS, PyQt5, GDAL/OGR and NumPy, all shipped with QGIS.

## Code style

Keep changes consistent with the surrounding code. A `pylintrc` is provided:

```bash
pylint --rcfile=pylintrc <file>
```

Run it inside a QGIS-aware Python environment (PyQGIS imports only resolve against the QGIS-bundled interpreter).

## Testing

Two layers — please cover both before opening a PR:

- **Unit tests** — the pure domain math (COMET cell cost, Darcy–Weisbach diameter, segment/booster splitting) lives in `src/core` with no QGIS dependency, so it runs with plain `pytest` — no QGIS, no display:

  ```bash
  pip install pytest numpy
  pytest tests/unit        # or: make test
  ```

  Add or update a test whenever you change that math. (Integration tests that drive QGIS/GRASS are not set up yet — see [#10](https://github.com/rpintassilgo/co2gis-qgis-plugin/issues/10).)

- **Manual testing** — because the plugin runs *inside* QGIS, always reload it and exercise the affected tab/workflow in QGIS before opening a PR. The in-dialog log panel helps. This is the primary check for anything touching the UI or the GRASS routing.

A `.pre-commit-config.yaml` is provided (Ruff lint + format); install [`pre-commit`](https://pre-commit.com/) and run `pre-commit install` once so checks run automatically on commit.

## Commits & pull requests

- Work on a branch in your fork, then open a pull request against `master`.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/) (`feat`, `fix`, `chore`, `docs`, `refactor`, …). Reference issues with a `Closes #N` footer where they apply.
- Keep pull requests focused — one logical change per PR, with a short description of what and why.
- Before opening the PR, run `pytest tests/unit` and make sure the plugin still loads and the affected workflow runs in QGIS (see [Testing](#testing)).

For commercial CCUS work needing custom development or priority support, reach out at **co2gis.support@gmail.com**.
