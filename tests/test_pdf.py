# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import importlib.util
import json
import lzma
import urllib.error
from argparse import Namespace
from pathlib import Path

import pdfplumber
import pikepdf
import pytest

from senfd.documents.plain import Figure, FromPdf
from senfd.pdf.pages import Pages, grid, spans
from senfd.pdf.reader import NotTagged, joined, read, stem_of
from senfd.pdf.tables import columns_of
from senfd.pdf.tree import Leaf
from senfd.tables import Cell, Row, Table

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


class Ruled:
    """A page with the borders given, in the place of Pages"""

    def __init__(self, verticals, horizontals):
        self.found = verticals, horizontals

    def verticals(self, number, box, pad=2.0):
        return self.found[0]

    def horizontals(self, number, box, pad=2.0):
        return self.found[1]


HEADER = [(112.0, 100.0, 180.0, 110.0), (230.0, 100.0, 260.0, 110.0)]
ROW = [(118.0, 120.0, 176.0, 130.0), (236.0, 120.0, 254.0, 130.0)]
# The rules of a two-row table from 72 to 300, the separator in two pieces
RULES = [
    (95.0, 72.0, 300.0),
    (115.0, 72.0, 219.8),
    (115.0, 220.4, 300.0),
    (135.0, 72.0, 300.0),
]


def test_a_border_far_from_the_centred_text_of_its_column_is_an_edge():
    # The first column is wide and its text centred, 40 pt from the border
    page = Ruled([(72.0, 95, 135), (220.0, 95, 135), (300.0, 95, 135)], RULES)
    assert columns_of(page, 0, HEADER + ROW, []).edges == [72.0, 220.0, 300.0]


def test_a_line_no_separator_reaches_is_no_edge():
    # A change bar in the margin, and the border of a table beside this one
    lines = [(72.0, 95, 135), (220.0, 95, 135), (300.0, 95, 135)]
    beside = [(336.0, 98, 112), (306.0, 95, 135)]
    page = Ruled(lines + beside, RULES)
    assert columns_of(page, 0, HEADER + ROW, []).edges == [72.0, 220.0, 300.0]


def test_a_table_whose_rows_no_rule_separates_has_the_borders_beside_its_text():
    text = [(80.0, 100.0, 180.0, 110.0), (230.0, 100.0, 290.0, 110.0)]
    page = Ruled(
        [(72.0, 95, 115), (220.0, 95, 115), (300.0, 95, 115), (336.0, 98, 112)],
        [(95.0, 72.0, 300.0), (115.0, 72.0, 300.0)],
    )
    assert columns_of(page, 0, text, []).edges == [72.0, 220.0, 300.0]


def test_a_cell_with_no_text_takes_a_column_no_other_covers():
    edges = [0.0, 50.0, 100.0]
    verticals = [(0.0, 0, 20), (50.0, 0, 20), (100.0, 0, 20)]
    assert spans([None, (55.0, 5.0, 95.0, 15.0)], edges, verticals) == [(0, 1), (1, 2)]


def one_page(path, content):
    """A PDF of one page drawing 'content' in Helvetica, its text in one
    piece of marked content"""

    pdf = pikepdf.new()
    page = pdf.add_blank_page(page_size=(300, 300))
    font = pdf.make_indirect(
        pikepdf.Dictionary(
            Type=pikepdf.Name.Font,
            Subtype=pikepdf.Name.Type1,
            BaseFont=pikepdf.Name.Helvetica,
        )
    )
    page.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font))
    page.Contents = pdf.make_stream(content.encode())
    pdf.save(path)
    return path


def marked_text(tmp_path, drawn):
    """The text the reader gives the marked content of a page drawing
    "Figure 338" at the baseline y 200, size 10, and then 'drawn'"""

    path = one_page(
        tmp_path / "page.pdf",
        "/P <</MCID 0>> BDC BT /F1 10 Tf 100 200 Td (Figure 338) Tj ET EMC " + drawn,
    )
    with pikepdf.open(path) as pdf, pdfplumber.open(path) as plumb:
        pages = Pages(plumb, {page.objgen: i for i, page in enumerate(pdf.pages)})
        text, _ = pages.text([[Leaf(pdf.pages[0].objgen, 0)]])
    return text


def test_text_struck_through_is_a_deletion_shown_and_not_read(tmp_path):
    # A rule 3 pt above the baseline, through the middle of the glyphs
    assert marked_text(tmp_path, "100 203 52 0.5 re f") == ""


def test_text_underlined_is_an_insertion_shown_and_read(tmp_path):
    # A rule 1 pt below the baseline, as an underline is drawn
    assert marked_text(tmp_path, "100 199 52 0.5 re f") == "Figure 338"


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


def page(*rows):
    """A table of 'rows', each a list of texts, a cell spanning the column
    before it written as None"""

    return Table(
        rows=[
            Row(
                cells=[
                    Cell(text=t) if t is not None else Cell(text="", merged="left")
                    for t in row
                ]
            )
            for row in rows
        ]
    )


def spanned(table):
    """'table' with the text of a spanning cell repeated, as the reader gives"""

    for row in table.rows:
        for before, cell in zip(row.cells, row.cells[1:]):
            if cell.merged == "left":
                cell.text = before.text
    return table


CAPTION_ROW = ["Figure 42: CSTS", None, None]


def test_the_caption_and_header_a_page_repeats_are_dropped_however_it_divides():
    first = spanned(
        page(CAPTION_ROW, ["Bits", "Type", "Description"], ["31:07", "RO", "Reserved"])
    )
    figure = Figure(
        figure_nr=42, caption="Figure 42: CSTS", description="CSTS", table=first
    )
    # The next page divides Description into two columns
    joined(
        figure,
        spanned(
            page(
                CAPTION_ROW + [None],
                ["Bits", "Type", "Description", None],
                ["06", "RO", "Shutdown Type", None],
            )
        ),
    )
    assert [r.cells[0].text for r in figure.table.rows] == [
        "Figure 42: CSTS",
        "Bits",
        "31:07",
        "06",
    ]


def test_a_row_broken_across_a_page_is_joined_again():
    first = spanned(
        page(CAPTION_ROW, ["Bits", "Type", "Description"], ["03:02", "RO", "SHST: a"])
    )
    figure = Figure(
        figure_nr=42, caption="Figure 42: CSTS", description="CSTS", table=first
    )
    joined(
        figure,
        spanned(
            page(
                CAPTION_ROW,
                ["Bits", "Type", "Description"],
                ["", "", "b"],
                ["01", "RO", "CFS"],
            )
        ),
    )
    rows = [[c.text for c in r.cells] for r in figure.table.rows[2:]]
    assert rows == [["03:02", "RO", "SHST: a\nb"], ["01", "RO", "CFS"]]


def test_the_rest_of_a_broken_row_goes_to_the_cell_it_is_the_rest_of():
    # The last cell spans two columns, and another cell has the same text
    first = spanned(
        page(
            CAPTION_ROW + [None],
            ["Bits", "Type", "Description", None],
            ["0", "RO", "0", None],
        )
    )
    figure = Figure(
        figure_nr=42, caption="Figure 42: CSTS", description="CSTS", table=first
    )
    joined(figure, spanned(page(["", "", "more", None])))
    assert [c.text for c in figure.table.rows[-1].cells] == [
        "0",
        "RO",
        "0\nmore",
        "0\nmore",
    ]


def test_a_row_with_text_before_its_last_cell_is_a_row_of_its_own():
    first = spanned(
        page(CAPTION_ROW, ["Bits", "Type", "Description"], ["03:02", "RO", "a"])
    )
    figure = Figure(
        figure_nr=42, caption="Figure 42: CSTS", description="CSTS", table=first
    )
    joined(figure, spanned(page(["", "RW", "b"])))
    assert [c.text for c in figure.table.rows[-1].cells] == ["", "RW", "b"]


def test_a_repeated_header_row_is_dropped_whichever_cells_it_merges_from_above():
    header = page(["Name", "Identifier", "Support", None])
    lower = Row(
        cells=[
            Cell(text="Name", merged="up"),
            Cell(text="I/O"),
            Cell(text="Admin"),
            Cell(),
        ]
    )
    header.rows.append(lower)
    first = spanned(page(["Figure 16: Features", None, None, None]))
    first.rows += spanned(header).rows + [
        page(["LBA Range Type", "03h", "O", "P"]).rows[0]
    ]
    figure = Figure(
        figure_nr=16, caption="Figure 16: Features", description="F", table=first
    )
    # The next page has the identifier merged from above, as the first lost it
    again = Row(
        cells=[
            Cell(text="Name", merged="up"),
            Cell(text="Identifier", merged="up"),
            Cell(text="I/O"),
            Cell(text="Admin"),
        ]
    )
    following = page(["Error Recovery", "05h", "M", "P"])
    joined(figure, Table(rows=[again] + following.rows))
    assert [r.cells[0].text for r in figure.table.rows[-2:]] == [
        "LBA Range Type",
        "Error Recovery",
    ]
