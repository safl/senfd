# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).parents[1] / "toolbox" / "record_cast.py"


@pytest.fixture(scope="module")
def record_cast():
    spec = importlib.util.spec_from_file_location("record_cast", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_command_is_typed_then_its_output_shown(record_cast):
    events = record_cast.events_of(["echo hello"], dict(os.environ))
    text = "".join(t for _, t in events)
    assert "echo hello\r\nhello\r\n" in text
    times = [at for at, _ in events]
    assert times == sorted(times)


def test_a_comment_is_typed_and_not_run(record_cast, tmp_path):
    marker = tmp_path / "ran"
    events = record_cast.events_of([f"# touch {marker}"], dict(os.environ))
    assert f"# touch {marker}" in "".join(t for _, t in events)
    assert not marker.exists()


def test_a_recording_is_the_same_each_time_it_is_made(
    record_cast, tmp_path, monkeypatch
):
    script = tmp_path / "script.sh"
    script.write_text("# Say hello\necho hello\n\nprintf 'a\\nb\\n'\n")
    casts = []
    for name in ("one.cast", "two.cast"):
        cast = tmp_path / name
        monkeypatch.setattr(sys, "argv", ["record_cast.py", str(script), str(cast)])
        assert record_cast.main() == 0
        casts.append(cast.read_text())
    assert casts[0] == casts[1]

    header, *events = casts[0].splitlines()
    assert json.loads(header)["version"] == 2
    assert all(json.loads(e)[1] == "o" for e in events)
    assert "a\r\nb\r\n" in "".join(json.loads(e)[2] for e in events)


def test_the_commands_are_asked_for_colour(record_cast, tmp_path, monkeypatch):
    script = tmp_path / "script.sh"
    script.write_text("echo colour=$FORCE_COLOR width=$COLUMNS\n")
    cast = tmp_path / "colour.cast"
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.setattr(sys, "argv", ["record_cast.py", str(script), str(cast)])
    assert record_cast.main() == 0
    assert f"colour=1 width={record_cast.WIDTH}" in cast.read_text()


def test_each_script_of_the_documentation_has_its_recording():
    """The pages load a recording by a path in raw HTML, which the docs build
    does not check"""

    root = Path(__file__).parents[1] / "docs"
    scripts = sorted(p.stem for p in (root / "casts").glob("*.sh"))
    assert "intro" in scripts
    for name in scripts:
        assert (root / "_static" / "casts" / f"{name}.cast").is_file(), name
