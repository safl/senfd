# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

from argparse import Namespace
from pathlib import Path

import pytest

import senfd.pipeline
from senfd.skiplist import MultipleClassifierMatchException

SKIP = """
[[skip]]
regex = ".*\\\\bData Pointer$"
matches = {matches}
description = "Not used here"
"""


def test_a_skip_list_leaves_out_the_figures_it_matches(tmp_path):
    import json

    skiplist = tmp_path / "skip.toml"
    skiplist.write_text(SKIP.format(matches=2), encoding="utf-8")

    path = Path("example") / "example.docx"
    senfd.pipeline.process(path, tmp_path, Namespace(skip_figures=skiplist))
    (normalized,) = tmp_path.glob("*.normalized.figure.document.json")
    document = json.loads(normalized.read_text(encoding="utf-8"))

    assert set(document["skipped"].values()) == {"Not used here"}
    assert len(document["skipped"]) == 2
    kinds = [f["subject"]["kind"] for f in document["figures"]]
    assert "data_pointer" not in kinds


def test_a_skip_list_matching_other_than_it_says_names_both_counts(tmp_path):
    skiplist = tmp_path / "skip.toml"
    skiplist.write_text(SKIP.format(matches=3), encoding="utf-8")

    path = Path("example") / "example.docx"
    with pytest.raises(MultipleClassifierMatchException, match="3 .* 2"):
        senfd.pipeline.process(path, tmp_path, Namespace(skip_figures=skiplist))
