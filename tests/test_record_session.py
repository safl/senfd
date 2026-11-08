# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).parents[1] / "toolbox" / "record_session.py"

# A program that asks, as an interactive one does, and says whether it reads
# from a terminal and how wide that is
ASKING = """
import os, shutil, sys
print("tty" if sys.stdin.isatty() else "pipe", shutil.get_terminal_size().columns)
while True:
    try:
        line = input("q> ")
    except EOFError:
        print("bye")
        break
    print("got", repr(line))
"""


@pytest.fixture(scope="module")
def record_session():
    spec = importlib.util.spec_from_file_location("record_session", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_each_line_is_typed_into_a_terminal_and_the_input_ends(record_session):
    command = [sys.executable, "-c", ASKING]
    events = record_session.events_of(command, ["one", "a\\tb"], dict(os.environ))
    text = "".join(t for _, t in events)
    assert f"tty {record_session.WIDTH}" in text
    assert "got 'one'" in text
    assert "got 'a\\tb'" in text  # '\t' in the script is a press of Tab
    assert text.rstrip().endswith("bye")
    times = [at for at, _ in events]
    assert times == sorted(times)


def test_the_recording_is_asciicast_v2(record_session, tmp_path, monkeypatch):
    script = tmp_path / "session.txt"
    script.write_text("hello\n")
    cast = tmp_path / "session.cast"
    command = f"{sys.executable} -c '{ASKING}'"
    monkeypatch.setattr(
        sys, "argv", ["record_session.py", command, str(script), str(cast)]
    )
    assert record_session.main() == 0
    lines = cast.read_text().splitlines()
    header = json.loads(lines[0])
    assert (header["version"], header["width"]) == (2, record_session.WIDTH)
    events = [json.loads(line) for line in lines[1:]]
    assert all(kind == "o" for _, kind, _ in events)
    assert "got 'hello'" in "".join(text for _, _, text in events)
