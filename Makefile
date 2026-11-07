# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

PROJECT_NAME:=senfd
PROJECT_VERSION:=$(shell sed -n 's/^__version__ = "\(.*\)"/\1/p' src/senfd/__init__.py)

BROWSER:=chromium-browser

.PHONY: dev all clean env build install uninstall test open format release

dev: env uninstall install-dev test open

env:
	pipx install build || true
	pipx install pre-commit || true
	pipx install twine || true

clean:
	@rm coverage.lcov || true
	@rm -r build || true
	@rm -r .coverage || true
	@rm -r dist|| true
	@rm -r htmlcov || true
	@rm -r .mypy_cache || true
	@rm -r .pytest_cache || true

uninstall:
	pipx uninstall $(PROJECT_NAME) || true

install-dev:
	pipx install --include-deps --force --editable .[dev]

install:
	pipx install --include-deps --force dist/*.tar.gz

build:
	pyproject-build

test:
	pytest --cov=$(PROJECT_NAME) --cov-fail-under=95 --cov-report=lcov --cov-report=term-missing --cov-report=html -vvs tests

release:
	twine upload dist/*

format:
	pre-commit run --all-files

kmdo:
	kmdo docs/src/usage/

version:
	./toolbox/project_version_update.py $(PROJECT_VERSION)
	make env uninstall build install
	$(PROJECT_NAME) --dump-schema --output /tmp/senfd_schemas
	cp /tmp/senfd_schemas/*.schema.json src/$(PROJECT_NAME)/schemas/
	senfd example/*.docx --output example/output
	rm -f example/output/*.error.log
	make
