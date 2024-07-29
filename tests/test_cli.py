#!/usr/bin/env python3
from pathlib import Path
from subprocess import run


def test_cli_tool(tmp_path):

    paths = list(Path("example").resolve().glob("*"))
    assert len(paths) > 0, "No documents available for testing"

    for path in paths:
        result = run(
            ["senfd", f"{path}", "--output", str(tmp_path)],
            capture_output=True,
            text=True,
        )

        assert not result.returncode, f"Got returncode: {result.returncode}"


def test_cli_tool_noargs(tmp_path):

    result = run(["senfd"], capture_output=True, text=True)

    assert result.returncode != 0, f"Should fail but did not: {result.returncode}"


def test_cli_tool_version(tmp_path):

    result = run(["senfd", "--version"], capture_output=True, text=True)

    assert not result.returncode


def test_cli_tool_dump_schema(tmp_path):

    result = run(["senfd", "--dump-schema"], capture_output=True, text=True)

    assert not result.returncode
