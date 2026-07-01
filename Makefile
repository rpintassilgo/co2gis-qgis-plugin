# CO2GIS — developer tasks.
#
# This is a QGIS plugin: it runs inside QGIS, there is no standalone entry point.
# These targets cover linting, the unit tests (pure domain logic in src/core, no
# QGIS required) and building the publishable plugin ZIP. The old QGIS
# plugin-builder targets (.ui / .qrc / nosetests / pylupdate) were removed —
# this project doesn't use that layout.

PLUGINNAME = co2gis

.PHONY: help test lint format zip

help:
	@echo "make test    - run the unit test suite (pytest, no QGIS required)"
	@echo "make lint    - run ruff lint checks"
	@echo "make format  - apply ruff formatting"
	@echo "make zip     - build the publishable plugin ZIP from HEAD"

test:
	pytest tests/unit

lint:
	ruff check .

format:
	ruff format .

# Mirrors the release workflow: top-level folder = co2gis, dev-only files dropped
# via export-ignore in .gitattributes.
zip:
	rm -f $(PLUGINNAME).zip
	git archive --format=zip --prefix=$(PLUGINNAME)/ -o $(PLUGINNAME).zip HEAD
	@echo "Created $(PLUGINNAME).zip"
