from argparse import Namespace
from pathlib import Path

import pytest

import senfd.pipeline
from senfd.skiplist import MultipleClassifierMatchException

SKIP = """
[[skip]]
regex = ".*Data Pointer$"
matches = {matches}
description = "Not used here"
"""


def test_a_skip_list_leaves_out_the_figures_it_matches(tmp_path):
    import json

    skiplist = tmp_path / "skip.toml"
    skiplist.write_text(SKIP.format(matches=2), encoding="utf-8")

    path = Path("example") / "example.docx"
    senfd.pipeline.process(path, tmp_path, Namespace(skip_figures=skiplist))
    (enriched,) = tmp_path.glob("*.enriched.figure.document.json")
    document = json.loads(enriched.read_text(encoding="utf-8"))

    assert len(document["skipped"]) == 2
    assert document["stats"]["skipped"] == 2
    assert not document["command_sqe_data_pointer"]
    # A SkipElement is a tuple of the pattern, the description and the count
    assert {e[1] for e in document["skip_map"].values()} == {"Not used here"}


def test_a_skip_list_matching_other_than_it_says_names_both_counts(tmp_path):
    skiplist = tmp_path / "skip.toml"
    skiplist.write_text(SKIP.format(matches=3), encoding="utf-8")

    path = Path("example") / "example.docx"
    with pytest.raises(MultipleClassifierMatchException, match="3 .* 2"):
        senfd.pipeline.process(path, tmp_path, Namespace(skip_figures=skiplist))
