# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import importlib.util
import json
import lzma
import urllib.error
from argparse import Namespace
from pathlib import Path

import pikepdf
import pytest

from senfd.documents.plain import FromPdf
from senfd.pdf.pages import grid, spans
from senfd.pdf.reader import NotTagged, read, stem_of

TOOL = Path(__file__).parents[1] / "toolbox" / "public_documents.py"


@pytest.fixture(scope="module")
def public():
    spec = importlib.util.spec_from_file_location("public_documents", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def document_named(public, name):
    """The public PDF of 'name', fetched into the cache; the test is skipped
    where it cannot be downloaded, and fails where it is not the one named"""

    document = next(d for d in public.documents() if d["name"] == name)
    try:
        return document, public.fetched(document)
    except (urllib.error.URLError, TimeoutError) as exc:
        pytest.skip(f"{document['url']} could not be downloaded: {exc}")


def test_a_pdf_is_named_as_the_docx_of_it_is():
    assert stem_of(
        Path("NVM-Express-Base-Specification-Revision-2.4-Ratified-2026.07.31.pdf")
    ) == ("NVM Express Base Specification, Revision 2-4 Ratified 2026-07-31")
    named = Path("NVM Express Base Specification, Revision 2.4 Ratified 2026.08.21.pdf")
    assert (
        stem_of(named)
        == "NVM Express Base Specification, Revision 2-4 Ratified 2026-08-21"
    )


def test_the_columns_are_the_borders_across():
    verticals = [(10.0, 0, 50), (10.9, 50, 90), (60.0, 0, 90), (110.0, 0, 90)]
    assert grid(verticals) == [10.0, 60.0, 110.0]


def test_a_cell_spans_the_columns_between_the_borders_beside_its_text():
    edges = [0.0, 50.0, 100.0, 150.0]
    verticals = [(0.0, 0, 20), (50.0, 0, 10), (100.0, 0, 20), (150.0, 0, 20)]
    # The first cell's text runs across the border at 50, which ends above it
    boxes = [(5.0, 12.0, 90.0, 18.0), (105.0, 12.0, 145.0, 18.0)]
    assert spans(boxes, edges, verticals) == [(0, 2), (2, 3)]


def test_a_cell_with_no_text_takes_a_column_no_other_covers():
    edges = [0.0, 50.0, 100.0]
    verticals = [(0.0, 0, 20), (50.0, 0, 20), (100.0, 0, 20)]
    assert spans([None, (55.0, 5.0, 95.0, 15.0)], edges, verticals) == [(0, 1), (1, 2)]


def test_a_pdf_without_a_structure_tree_is_refused(tmp_path):
    untagged = tmp_path / "untagged.pdf"
    pdf = pikepdf.new()
    pdf.add_blank_page()
    pdf.save(untagged)
    with pytest.raises(NotTagged, match="no structure tree"):
        read(untagged)
    assert FromPdf.is_applicable(untagged)
    with pytest.raises(NotTagged):
        FromPdf.convert(untagged, Namespace())


@pytest.mark.parametrize("name", ["Key Value Command Set 1.4", "NVM Command Set 1.3"])
def test_a_published_pdf_gives_the_data_model_its_manifest_says(public, name, tmp_path):
    document, path = document_named(public, name)
    found = public.counts(public.made(path, tmp_path))
    assert found == {key: document[key] for key in public.COUNTED}


def test_a_published_pdf_reads_as_its_figures(public, tmp_path):
    _, path = document_named(public, "NVM Command Set 1.3")
    figures, errors = read(path)
    assert figures.meta.stem.startswith("NVM Express NVM Command Set Specification")
    assert len(figures.figures) > 150
    # Every figure has its section, by the outline, and its page, by the table
    # of figures, as the .docx gives them
    assert all(f.section for f in figures.figures)
    assert all(f.page_nr for f in figures.figures)
    write = public.made(path, tmp_path)["command_sets"]["nvm"]["commands"]["write"]
    cdw12 = next(d for d in write["sqe"] if d["lower"] == 12)
    fua = next(f for f in cdw12["fields"] if f.get("acronym") == "FUA")
    assert (fua["upper"], fua["lower"], write["opcode"]) == (30, 30, 1)


def test_the_compressed_data_model_is_the_same_bytes_every_time(public, tmp_path):
    model = tmp_path / "merged.spec.document.json"
    model.write_text(json.dumps({}), encoding="utf-8")
    first = public.compressed(model).read_bytes()
    assert public.compressed(model).read_bytes() == first
    assert lzma.decompress(first) == model.read_bytes()


def test_a_wrong_answer_of_the_benchmark_is_counted_and_named(public, tmp_path, capsys):
    lane = tmp_path / "lane.json"
    answers = [
        {"id": 1, "question": "Write?", "answer": "| Write | 01h |"},
        {"id": 2, "question": "Wrong?", "answer": "| Write | 7Fh |"},
    ]
    lane.write_text(json.dumps({"answers": answers}), encoding="utf-8")
    tally = public.graded(lane)
    assert tally["right"] + tally["wrong"] + tally["unknown"] == 2
    assert tally["right"] < 2 and "2: " in capsys.readouterr().out
