# The builddir path is hardcoded in the config/doxy.conf and config/conf.py
PROJECT_NAME:=senfd
BUILD_DIR?=_build
CONFIG_DIR?=./
DOCS_DIR?=src

VENV_NAME = .venv
VENV = . ${VENV_NAME}/bin/activate && 
PYTHON = ${VENV} python3

default: clean deps html serve

.PHONY: clean deps kmdo html linkcheck serve

clean:
	rm -fr $(BUILD_DIR) || true	

deps:
	pipx install poetry
	poetry config keyring.enabled false
	poetry install --no-root

kmdo:
	kmdo .

html:
	mkdir -p $(BUILD_DIR)/html
	PATH="$(PATH):../src" ${PYTHON} -m sphinx -E -b html -c $(CONFIG_DIR) $(DOCS_DIR) $(BUILD_DIR)
	touch $(BUILD_DIR)/html/.nojekyll

linkcheck:
	PATH="$(PATH):../src" ${PYTHON} -m sphinx -b linkcheck -c $(CONFIG_DIR) $(DOCS_DIR) $(BUILD_DIR)

serve:
	@screen -S $(PROJECT_NAME)docs -X kill || echo "Could not kill server, probably not running"
	@cd $(BUILD_DIR) && screen -S $(PROJECT_NAME)docs -d -m python3 -m http.server 8888
