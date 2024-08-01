PROJECT_NAME:=senfd
PROJECT_VERSION:=0.2.3

BROWSER:=chromium-browser

.PHONY: all clean env build install uninstall test open format release

all: env uninstall build install test open

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

build:
	pyproject-build

install:
	pipx install --include-deps --force .[dev]

uninstall:
	pipx uninstall $(PROJECT_NAME) || true

test:
	pytest --cov=$(PROJECT_NAME) --cov-report=lcov --cov-report=term-missing --cov-report=html -vvs tests

open:
	$(BROWSER) /tmp/pytest-of-${USER}/pytest-current/test_cli_tool0/*.{html,json} || true

format:
	pre-commit run --all-files

release:
	twine upload dist/*

kmdo:
	kmdo docs/src/usage/

version:
	./toolbox/project_version_update.py $(PROJECT_VERSION)
	make env uninstall build install
	$(PROJECT_NAME) --dump-schema --output /tmp/senfd_schemas
	cp /tmp/senfd_schemas/*.schema.json src/$(PROJECT_NAME)/schemas/
	senfd example/* --output example/output
	make
