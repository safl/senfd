#!/usr/bin/env python3

# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import os
import sys
from pathlib import Path
from subprocess import run


def test_cli_tool(tmp_path):
    paths = list(Path("example").resolve().glob("*.docx"))
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


def senfd_main(monkeypatch, *args):
    """Run the command-line entrypoint in this process, as 'senfd *args'"""

    import senfd.cli

    monkeypatch.setattr("sys.argv", ["senfd", *map(str, args)])
    return senfd.cli.main()


def test_the_documents_and_their_merged_model_are_written(tmp_path, monkeypatch):
    import json

    docs = sorted(Path("example").glob("*.docx"))
    assert senfd_main(monkeypatch, *docs, "--output", tmp_path) == 0

    for doc in docs:
        assert (tmp_path / f"{doc.stem}.error.log").is_file()
    merged = "merged.spec.document.json"
    expected = Path("example") / "output" / merged
    assert json.loads((tmp_path / merged).read_text(encoding="utf-8")) == json.loads(
        expected.read_text(encoding="utf-8")
    )


def test_the_version_and_the_schemas_are_printed_in_process(
    tmp_path, monkeypatch, capsys
):
    import senfd

    assert senfd_main(monkeypatch, "--version", "--output", tmp_path) == 0
    assert capsys.readouterr().out.strip() == senfd.__version__

    assert senfd_main(monkeypatch, "--dump-schema", "--output", tmp_path) == 0
    assert sorted(p.name for p in tmp_path.glob("*.schema.json")) == sorted(
        p.name for p in Path("src/senfd/schemas").glob("*.schema.json")
    )


def test_a_merged_model_already_in_the_output_is_not_merged_again(
    tmp_path, monkeypatch
):
    """A rerun into the same folder makes the merged model anew, rather than
    keeping the commands of the merged model it finds there"""

    import json

    docs = sorted(Path("example").glob("*.docx"))
    assert senfd_main(monkeypatch, *docs, "--output", tmp_path) == 0
    merged = tmp_path / "merged.spec.document.json"
    first = json.loads(merged.read_text(encoding="utf-8"))

    stale = dict(first, command_sets={"stale": {"alias": "stale", "name": "Stale"}})
    stale["command_sets"]["stale"]["commands"] = {
        "gone": {"opcode": 1, "alias": "gone", "name": "Gone"}
    }
    merged.write_text(json.dumps(stale), encoding="utf-8")

    assert senfd_main(monkeypatch, *docs, "--output", tmp_path) == 0
    assert json.loads(merged.read_text(encoding="utf-8")) == first


def test_a_run_says_what_it_made_and_what_to_look_at(tmp_path):
    documents = sorted(str(p) for p in Path("example").resolve().glob("*.docx"))
    result = run(
        ["senfd", *documents, "--output", str(tmp_path)], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert f"{len(documents)} documents into" in result.stdout
    assert "candidate errata" in result.stdout and "document errors" in result.stdout
    assert f"senfd lint --spec {tmp_path / 'merged.spec.document.json'}" in (
        result.stdout
    )
    listed = run(
        ["senfd", "lint", "--spec", str(tmp_path / "merged.spec.document.json")],
        capture_output=True,
        text=True,
    )
    assert listed.returncode == 0
    assert listed.stdout.startswith("The authors': candidate errata")
    errata = run(
        ["senfd", "errata", "--spec", str(tmp_path / "merged.spec.document.json")],
        capture_output=True,
        text=True,
    )
    assert errata.returncode == 0 and "beyond the 64 bits" in errata.stdout
    logs = sorted(p.name for p in tmp_path.glob("*.error.log"))
    assert logs and all("." not in name.removesuffix(".error.log") for name in logs)


def test_cli_tool_help_is_the_one_the_documentation_shows():
    """docs/src/usage/usage.out is what kmdo wrote of senfd --help"""

    result = run(
        ["senfd", "--help"],
        capture_output=True,
        text=True,
        env={**os.environ, "COLUMNS": "80"},
    )

    assert not result.returncode
    assert result.stdout == Path("docs/src/usage/usage.out").read_text()


def test_running_the_module_exits_with_the_status_of_main(tmp_path):
    result = run(
        [sys.executable, "-m", "senfd.cli", str(tmp_path / "missing.pdf")],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "senfd: no such document" in result.stderr
