import json
from argparse import Namespace
from pathlib import Path

import senfd.pipeline


def model_of(path, tmp_path):
    """The model document senfd makes of the document at 'path'"""

    senfd.pipeline.process(path, tmp_path, Namespace(skip_figures=None))
    (model,) = tmp_path.glob(f"{path.stem}.model.document.json")
    return json.loads(model.read_text(encoding="utf-8"))


def test_a_command_has_its_dwords_its_dword_pairs_and_its_pointers(tmp_path):
    model = model_of(Path("example") / "example.docx", tmp_path)
    ding = model["command_sets"]["foobar"]["commands"]["ding"]

    dwords = {
        (sqe["lower"], sqe["upper"]): (sqe["nbytes"], sqe["condition"])
        for sqe in ding["sqe"]
    }
    assert dwords == {
        (2, 3): (8, None),
        (4, 5): (8, None),
        (6, 9): (16, None),
        (10, 10): (4, None),
        (11, 11): (4, "Foo Mode is set"),
        (14, 15): (8, None),
    }
    (pair,) = [sqe for sqe in ding["sqe"] if sqe["lower"] == 2]
    assert [(f["upper"], f["lower"], f["acronym"]) for f in pair["fields"]] == [
        (63, 0, "faddr")
    ]


def test_a_row_heading_the_rows_below_it_is_not_a_field(tmp_path):
    model = model_of(Path("example") / "example.docx", tmp_path)
    dong = model["command_sets"]["foobar"]["commands"]["dong"]

    (cdw10,) = [sqe for sqe in dong["sqe"] if sqe["lower"] == 10]
    assert [f["acronym"] for f in cdw10["fields"]] == [None, "bk"]


def test_a_command_gets_the_dwords_another_document_describes(tmp_path):
    """A command set specification can list a command whose dwords the base
    specification describes; the merged model gives the command those dwords"""

    import runpy

    import senfd.documents.merged

    toolbox = runpy.run_path("toolbox/example_docx.py")
    other = tmp_path / "docx" / "other.docx"
    other.parent.mkdir()
    toolbox["write"](
        other,
        [
            (
                "Opcodes for Bar Command Set Commands",
                {
                    "header": (
                        "Function",
                        "Data Transfer",
                        "Combined Opcode",
                        "Command",
                        "Reference",
                    ),
                    "rows": [("0000 00b", "01b", "81h", "Zap", "2.1")],
                },
            )
        ],
    )
    example = model_of(Path("example") / "example.docx", tmp_path)
    assert [sqe["command_alias"] for sqe in example["sqe_of_other_documents"]] == [
        "zap"
    ]
    model_of(other, tmp_path)

    merged, _ = senfd.documents.merged.FromFolder.convert(tmp_path, Namespace())
    zap = merged.command_sets["bar"].commands["zap"]
    assert [(sqe.lower, sqe.fields[0].acronym) for sqe in zap.sqe] == [(10, "zcnt")]
    assert not merged.sqe_of_other_documents
