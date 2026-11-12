# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

PROJECT_NAME:=senfd
PROJECT_VERSION:=$(shell sed -n 's/^__version__ = "\(.*\)"/\1/p' src/senfd/__init__.py)

BROWSER:=chromium-browser

.PHONY: dev all clean env build install uninstall test open format release refresh benchmark

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
	pipx install --include-deps --force --editable ".[dev]"

install:
	pipx install --include-deps --force dist/*.tar.gz

build:
	pyproject-build

test:
	pytest --cov=$(PROJECT_NAME) --cov-fail-under=95 --cov-report=lcov --cov-report=term-missing --cov-report=html -vvs tests benchmark/tests

release:
	twine upload dist/*

# The recordings and screenshots the README and the documentation show, made
# again with the senfd of this checkout from the PDFs in ~/specs, into
# ~/.cache/senfd. The recording of sate --llm needs llama-server on port 8088.
SPECS?=$(HOME)/specs
LLM?=http://127.0.0.1:8088
CASTS:=docs/_static/casts

refresh:
	@python3 -c "import senfd, sys; sys.exit(not senfd.__file__.startswith('$(CURDIR)/'))" \
		|| (echo "refresh: python3 does not import the senfd of $(CURDIR)"; exit 1)
	@ls $(SPECS)/*.pdf > /dev/null || (echo "refresh: no PDFs in $(SPECS)"; exit 1)
	@curl -sf $(LLM)/health > /dev/null \
		|| (echo "refresh: no llama-server at $(LLM), which $(CASTS)/llm.cast needs"; exit 1)
	python3 toolbox/record_cast.py docs/casts/intro.sh $(CASTS)/intro.cast
	python3 toolbox/record_cast.py docs/casts/lint.sh $(CASTS)/lint.cast
	python3 toolbox/record_cast.py docs/casts/llm.sh $(CASTS)/llm.cast
	python3 toolbox/record_session.py "sate" docs/casts/session.txt $(CASTS)/session.cast
	python3 toolbox/cast_svg.py $(CASTS)/session.cast $(CASTS)/session.svg
	python3 toolbox/web_screenshots.py --spec $(HOME)/.cache/senfd/merged.spec.document.json docs/_static/web

# The benchmark, as benchmark/README.md describes it, of the senfd release this
# checkout is, into $(RESULTS)/<date>-v<version>, a repository of its own
BENCHMARK_CONFIG?=configs/default.toml
RESULTS?=$(HOME)/git/senfd-results

benchmark:
	@cd benchmark && grep -q '^commit = "v$(PROJECT_VERSION)"' $(BENCHMARK_CONFIG) \
		|| (echo "benchmark: $(BENCHMARK_CONFIG) does not pin senfd v$(PROJECT_VERSION)"; exit 1)
	@test -d $(RESULTS) || (echo "benchmark: no directory $(RESULTS) for the records"; exit 1)
	cd benchmark && cijoe workflows/benchmark.yaml -c $(BENCHMARK_CONFIG) \
		-o $(RESULTS)/$$(date +%F)-v$(PROJECT_VERSION)

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
