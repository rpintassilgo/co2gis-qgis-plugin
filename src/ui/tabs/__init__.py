"""The dialog's tab modules — one per tab of the 7-tab pipeline.

Each module follows the same function pattern (no classes): ``setup_<tab>_tab``
builds the widgets onto the dialog, ``connect_<tab>_signals`` wires them, and the
tab's ``prepare``/``publish`` handlers sit alongside. ``networks_ui`` is the LCP
tab's Network-mode page. Non-tab UI (e.g. ``settings_dialog``) stays in ``src/ui/``.
"""
