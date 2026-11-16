# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


def recipe(target: str) -> str:
    """The lines of the recipe of 'target' in the Makefile"""

    text = (ROOT / "Makefile").read_text()
    match = re.search(rf"^{target}:.*\n((?:\t.*\n)+)", text, re.M)
    assert match, f"no target {target}"
    return match[1]


def test_make_refresh_records_every_script_of_docs_casts():
    refresh = recipe("refresh")
    for script in sorted((ROOT / "docs" / "casts").iterdir()):
        cast = f"$(CASTS)/{script.stem}.cast"
        assert f"docs/casts/{script.name} {cast}" in refresh, script.name


def test_make_refresh_takes_the_screenshots_in_the_default_theme():
    from senfd.sate import web

    tool = (ROOT / "toolbox" / "web_screenshots.py").read_text()
    assert "toolbox/web_screenshots.py" in recipe("refresh")
    assert f'THEME = "{next(iter(web.THEMES))}"' in tool


@pytest.mark.skipif(shutil.which("make") is None, reason="make is not installed")
def test_make_benchmark_refuses_a_configuration_of_another_release(tmp_path):
    config = tmp_path / "other.toml"
    config.write_text('[senfd]\ncommit = "v0.0.1"\n')

    done = subprocess.run(
        ["make", "-s", "benchmark", f"BENCHMARK_CONFIG={config}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert done.returncode != 0
    assert "does not pin senfd" in done.stdout + done.stderr


@pytest.mark.skipif(shutil.which("make") is None, reason="make is not installed")
def test_make_benchmark_refuses_a_directory_for_the_records_that_does_not_exist(
    tmp_path,
):
    import senfd

    config = tmp_path / "this.toml"
    config.write_text(f'[senfd]\ncommit = "v{senfd.__version__}"\n')

    done = subprocess.run(
        [
            "make",
            "-s",
            "benchmark",
            f"BENCHMARK_CONFIG={config}",
            f"RESULTS={tmp_path / 'missing'}",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert done.returncode != 0
    assert "for the records" in done.stdout + done.stderr


def test_the_screenshots_of_the_map_show_the_cns_values_of_identify():
    """docs/src/index.rst shows web-map-light.png and web-map-dark.png beside
    the screenshots of the question page"""

    import runpy

    import senfd.query
    from senfd.documents.spec import SpecDocument

    tool = runpy.run_path(str(ROOT / "toolbox" / "web_screenshots.py"))
    out = Path("docs/_static/web")
    assert [p.name for p in tool["names"](out, "map")] == [
        "web-map-light.png",
        "web-map-dark.png",
    ]
    assert [p.name for p in tool["names"](out)] == ["web-light.png", "web-dark.png"]
    spec = senfd.query.load(ROOT / "example" / "output" / "merged.spec.document.json")
    assert tool["focus"](spec) == "val:example:26"
    assert tool["focus"](SpecDocument()) == "home"


def test_ci_installs_the_browser_before_the_tests_of_the_map():
    """tests/test_sate_map_browser.py is skipped without the browser, so CI
    must install it before it runs the tests"""

    workflow = (ROOT / ".github" / "workflows" / "bd.yaml").read_text()
    installed = workflow.find("playwright install --with-deps chromium-headless-shell")
    assert 0 < installed < workflow.find("make test")
