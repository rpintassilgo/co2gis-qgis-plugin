"""Domain / processing logic, importable without Qt.

Modules here hold the COMET cost model, LCP routing and CAPEX computation. They
must not access widgets, so they are safe to call off the UI thread and can be
unit-tested without instantiating the dialog.
"""
