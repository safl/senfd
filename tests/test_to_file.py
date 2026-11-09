# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import os

from senfd.documents.base import to_file

CONTENT = "foo bar baz"
FILENAME = "testtofile.txt"


def test_to_file_without_a_path(tmp_path):
    orig = os.getcwd()
    os.chdir(tmp_path)

    path = to_file(CONTENT, FILENAME)
    back = path.read_text(encoding="utf-8")

    os.chdir(orig)
    assert back == CONTENT


def test_to_file_with_a_dirpath(tmp_path):
    path = to_file(CONTENT, FILENAME, tmp_path)
    back = path.read_text(encoding="utf-8")

    assert back == CONTENT


def test_to_file_with_a_filepath(tmp_path):
    path = to_file(CONTENT, FILENAME, tmp_path / FILENAME)
    back = path.read_text(encoding="utf-8")

    assert back == CONTENT


def test_the_example_outputs_are_those_senfd_makes(tmp_path):
    """example/output is what 'make version' writes; a change to what senfd
    makes of the example documents shows here, rather than going unseen. They
    are compared byte for byte, as the JSON is written to be diffed: indented,
    and the same bytes of the same document every time"""

    from argparse import Namespace
    from pathlib import Path

    import senfd.pipeline

    for path in sorted(Path("example").glob("*.docx")):
        senfd.pipeline.process(path, tmp_path, Namespace(skip_figures=None))

    committed = sorted(Path("example/output").glob("*.document.json"))
    assert committed
    for expected in committed:
        if expected.name.startswith("merged."):
            continue
        made = tmp_path / expected.name
        assert made.read_text(encoding="utf-8") == expected.read_text(
            encoding="utf-8"
        ), f"{expected} is not what senfd makes; regenerate it with 'make version'"


def test_the_example_is_the_one_the_toolbox_writes(tmp_path):
    """example/example.docx is written by toolbox/example_docx.py; edit the
    script rather than the document"""

    import json
    import runpy
    import sys
    from argparse import Namespace
    from pathlib import Path

    import senfd.pipeline

    path = tmp_path / "docx" / "example.docx"
    path.parent.mkdir()
    argv, sys.argv = sys.argv, ["example_docx.py", str(path)]
    try:
        runpy.run_path("toolbox/example_docx.py", run_name="__main__")
    finally:
        sys.argv = argv
    senfd.pipeline.process(path, tmp_path, Namespace(skip_figures=None))

    name = "example.plain.figure.document.json"
    made = json.loads((tmp_path / name).read_text(encoding="utf-8"))
    expected = json.loads((Path("example/output") / name).read_text(encoding="utf-8"))
    # The document knows the file it was made from, through every stage; the
    # file written here is not byte for byte the committed one, so its hash
    # is checked against itself and left out of the comparison
    import hashlib

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert (made["meta"]["file"], made["meta"]["sha256"]) == ("example.docx", digest)
    spec = json.loads(
        (tmp_path / "example.spec.document.json").read_text(encoding="utf-8")
    )
    assert spec["documents"]["example"]["sha256"] == digest
    made["meta"]["sha256"] = expected["meta"]["sha256"]
    assert made == expected
