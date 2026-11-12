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
