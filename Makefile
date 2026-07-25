# Convenience wrappers around the supported build path.
#
# The single supported build is cx_Freeze via setup.py (see ADR-001). This file
# previously invoked `python setup.py py2exe`, which has never worked with this
# project's setup.py and only produced a confusing error.
#
# Prerequisites: pip install -r requirements.txt, plus a built front-end
# (client/dist) and, on Windows, an extracted ./electron runtime.

PYTHON ?= python3

.PHONY: help deps client build test lint clean

help:
	@echo "make deps    - install pinned Python dependencies"
	@echo "make client  - build the Vue front-end into client/dist"
	@echo "make build   - freeze the application with cx_Freeze (setup.py build)"
	@echo "make test    - run the Python test suite"
	@echo "make lint    - lint the Vue front-end"
	@echo "make clean   - remove build artifacts and caches"

deps:
	$(PYTHON) -m pip install -r requirements.txt

client:
	cd client && npm ci && npm run build

build: client
	$(PYTHON) setup.py build

test:
	$(PYTHON) -m pytest

lint:
	cd client && npm run lint

clean:
	rm -rf build/ dist/ windows/
	find src -name '__pycache__' -type d -prune -exec rm -rf {} +
	find . -name '*~' -delete
