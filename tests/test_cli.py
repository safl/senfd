#!/usr/bin/env python3

# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

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
    assert "candidate errata (senfd-query errata)" in result.stdout
    logs = sorted(p.name for p in tmp_path.glob("*.error.log"))
    assert logs and all("." not in name.removesuffix(".error.log") for name in logs)
