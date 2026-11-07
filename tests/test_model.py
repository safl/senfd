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
