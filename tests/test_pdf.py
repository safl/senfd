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
from senfd.pdf.reader import (
    NotTagged,
    Section,
    joined,
    outline,
    read,
    section_at,
    stem_of,
)
from senfd.pdf.tables import Columns, astray, bordered, columns_of, unwrapped
from senfd.pdf.tree import Leaf, contents, paragraphs
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


def test_the_borders_of_a_cell_holding_a_table_are_not_the_table_s():
    # As Figure 49 of the Zoned Namespace Command Set 1.5: the table nested in
    # the third column stands 2.2 points inside the borders of its cell
    cell = [(72.0, 95, 135), (166.6, 95, 135), (468.1, 95, 135), (523.4, 95, 135)]
    table = [(168.8, 100, 133), (200.4, 100, 133), (465.9, 100, 133)]
    rules = [(95.0, 72.0, 523.4), (98.0, 72.0, 523.4), (135.0, 72.0, 523.4)]
    text = [(80.0, 96.0, 120.0, 97.0), (172.0, 99.0, 460.0, 134.0)]
    nested = [bordered(168.8, 100.0, 465.9, 133.0)]
    assert columns_of(Ruled(cell + table, rules), 0, text, nested).edges == [
        72.0,
        166.6,
        468.1,
        523.4,
    ]

    # Nor are they the nested table's own, its rules ending at its own borders
    rules = [(100.0, 169.0, 465.6), (116.0, 169.0, 465.6), (133.0, 169.0, 465.6)]
    text = [(172.0, 101.0, 460.0, 115.0), (172.0, 117.0, 460.0, 132.0)]
    assert columns_of(Ruled(cell + table, rules), 0, text, []).edges == [
        168.8,
        200.4,
        465.9,
    ]


def test_a_rule_beside_a_nested_table_does_not_separate_its_rows():
    # As Figure 35 of the Zoned Namespace Command Set 1.5: a table of values in
    # the second column of a table that is itself in a cell. The rule between
    # two rows of that table's first column lies beside the table of values,
    # and ends at borders that are not the table of values' own.
    holding = [(120.1, 450, 710), (193.4, 450, 710), (517.5, 450, 710)]
    table = [(200.7, 467, 688), (256.5, 467, 688), (513.1, 467, 688)]
    rules = [
        (467.2, 200.9, 512.9),
        (478.2, 200.9, 512.9),
        (543.2, 200.9, 512.9),
        (547.5, 120.5, 193.0),
        (687.8, 200.9, 512.9),
    ]
    text = [
        (212.0, 469.0, 240.0, 477.0),
        (262.0, 469.0, 510.0, 477.0),
        (212.0, 480.0, 240.0, 542.0),
        (262.0, 480.0, 510.0, 542.0),
        (212.0, 552.0, 240.0, 686.0),
        (262.0, 552.0, 510.0, 686.0),
    ]
    assert columns_of(Ruled(holding + table, rules), 0, text, []).edges == [
        200.7,
        256.5,
        513.1,
    ]


def test_the_content_of_a_table_includes_its_nested_tables():
    """The text of a table nested two levels deep does not belong to the
    outermost cell. read_cell() finds that text from the marked content
    under the table."""

    def element(kind, *kids):
        return pikepdf.Dictionary(S=pikepdf.Name(f"/{kind}"), K=pikepdf.Array(kids))

    def table(*cells):
        return element("Table", element("TR", *[element("TD", *c) for c in cells]))

    innermost = table([element("P", 3)])
    inner = table([element("P", 1)], [element("P", 2), innermost])
    page = (1, 0)

    assert contents(inner, page) == [Leaf(page, 1), Leaf(page, 2), Leaf(page, 3)]
    assert paragraphs(inner, page) == [[Leaf(page, 1)], [Leaf(page, 2)]]


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


def struck_pages(tmp_path, drawn):
    """The Pages of a page drawing "Figure 338" and then 'drawn'"""

    path = one_page(
        tmp_path / "page.pdf",
        "/P <</MCID 0>> BDC BT /F1 10 Tf 100 200 Td (Figure 338) Tj ET EMC " + drawn,
    )
    with pikepdf.open(path) as pdf, pdfplumber.open(path) as plumb:
        pages = Pages(plumb, {page.objgen: i for i, page in enumerate(pdf.pages)})
        return pages.deletions()


def test_an_evicted_page_is_read_again_with_the_same_result(tmp_path, monkeypatch):
    monkeypatch.setattr("senfd.pdf.pages.HELD", 1)
    pdf = pikepdf.new()
    font = pdf.make_indirect(
        pikepdf.Dictionary(
            Type=pikepdf.Name.Font,
            Subtype=pikepdf.Name.Type1,
            BaseFont=pikepdf.Name.Helvetica,
        )
    )
    # The first page also has a struck-through deletion
    struck = " BT /F1 10 Tf 100 100 Td (Gone) Tj ET 100 103 30 0.5 re f"
    for number in range(3):
        page = pdf.add_blank_page(page_size=(300, 300))
        page.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font))
        drawn = (
            f"/P <</MCID 0>> BDC BT /F1 10 Tf 100 200 Td (Figure {number}) Tj ET EMC"
        )
        page.Contents = pdf.make_stream(
            (drawn + (struck if not number else "")).encode()
        )
    pdf.save(tmp_path / "pages.pdf")

    with (
        pikepdf.open(tmp_path / "pages.pdf") as pdf,
        pdfplumber.open(tmp_path / "pages.pdf") as plumb,
    ):
        pages = Pages(plumb, {page.objgen: i for i, page in enumerate(pdf.pages)})
        leaves = [[[Leaf(page.objgen, 0)]] for page in pdf.pages]
        read = [pages.text(leaf)[0] for leaf in leaves + leaves[:1]]
        held = len(pages._chars)
        deleted = pages.deletions()

    assert read == ["Figure 0", "Figure 1", "Figure 2", "Figure 0"]
    assert held == 1
    assert deleted is not None and "4 characters in 1 place on 1 page" in deleted


def test_a_deletion_shown_is_counted_and_quoted(tmp_path):
    said = struck_pages(tmp_path, "100 203 52 0.5 re f")
    assert said is not None
    assert "10 characters in 1 place on 1 page of the file" in said
    assert said.endswith("the first on page 1: 'Figure 338'")


def test_a_line_drawn_through_a_label_strikes_nothing(tmp_path):
    # An arrow of a diagram, stroked through the middle of its label
    assert marked_text(tmp_path, "90 203 m 162 203 l S") == "Figure 338"
    assert struck_pages(tmp_path, "90 203 m 162 203 l S") is None


def test_a_page_with_no_deletion_shown_says_nothing(tmp_path):
    assert struck_pages(tmp_path, "100 199 52 0.5 re f") is None


def test_reading_a_pdf_reports_its_deletions_shown_as_an_error(tmp_path):
    path = one_page(
        tmp_path / "page.pdf",
        "/P <</MCID 0>> BDC BT /F1 10 Tf 100 200 Td (Figure 338) Tj ET EMC "
        "100 203 52 0.5 re f",
    )
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        pdf.Root.StructTreeRoot = pdf.make_indirect(
            pikepdf.Dictionary(Type=pikepdf.Name.StructTreeRoot, K=pikepdf.Array())
        )
        pdf.save(path)
    _, errors = read(path)
    assert [e.message for e in errors if "struck through" in e.message] == [
        "Text struck through, a deletion of tracked changes shown, left out: "
        "10 characters in 1 place on 1 page of the file, the first on page 1: "
        "'Figure 338'"
    ]


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
    # And the page of the file, which a link to the PDF opens at
    assert all(f.pdf_page for f in figures.figures)
    write = public.made(path, tmp_path)["command_sets"]["nvm"]["commands"]["write"]
    cdw12 = next(d for d in write["sqe"] if d["lower"] == 12)
    fua = next(f for f in cdw12["fields"] if f.get("acronym") == "FUA")
    assert (fua["upper"], fua["lower"], write["opcode"]) == (30, 30, 1)


def test_a_table_nested_two_levels_deep_is_read_as_a_table(public):
    """Figure 35 of the Zoned Namespace Command Set 1.5 has a table of two
    columns in the cell of bits 15:08, and a table of values in a cell of
    that table. The text of the table of values does not belong to the cell
    of bits 15:08, and both tables have two columns."""

    _, path = document_named(public, "Zoned Namespace Command Set 1.5")
    figures, _ = read(path)
    (figure,) = [f for f in figures.figures if f.figure_nr == 35]
    row = next(r for r in figure.table.rows if r.cells[0].text == "15:08")
    cell = row.cells[1]
    (inner,) = cell.tables
    (innermost,) = inner.rows[1].cells[1].tables

    assert "\n".join(cell.text.split()) == "Zone\nReceive\nAction\nSpecific\n(ZRAS):"
    assert {len(r.cells) for r in inner.rows} == {2}
    assert {len(r.cells) for r in innermost.rows} == {2}
    assert [c.text for c in innermost.rows[0].cells] == ["Value", "Definition"]
    # The cell holding the table of values is the cell of two rows
    assert [r.cells[1].merged for r in inner.rows] == [None, None, "up", None]


def test_the_zns_pdf_gives_the_cases_of_zras(public, tmp_path):
    """ZRAS, bits 15:08 of Command Dword 13 of Zone Management Receive,
    depends on the value of ZRA. The table of values nested in the table of
    cases holds the values of the first case."""

    _, path = document_named(public, "Zoned Namespace Command Set 1.5")
    described = public.made(path, tmp_path)["dwords"]["zone_management_receive"]
    cdw13 = next(d for d in described if d["lower"] == 13)
    zras = next(f for f in cdw13["fields"] if f["acronym"] == "ZRAS")
    first, others = zras["cases"]

    assert zras["values"] == [] and "Value" not in zras["description"]
    assert (first["selector"], [w["value"] for w in first["when"]]) == ("ZRA", [0, 1])
    assert [v["value"] for v in first["values"]][:3] == ["0h", "1h", "2h"]
    assert (others["otherwise"], others["role"]) == (True, "reserved")


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


def test_the_pages_of_a_figure_are_joined_in_their_order_not_their_tags():
    """As byte 261 of Base 2.4's Identify Controller, a row filling a page of
    its own, which Word tags as a table after the rest of the figure"""

    from senfd.pdf.reader import assembled

    header = ["Bytes", "Type", "Description"]
    figure = Figure(
        figure_nr=42,
        caption="Figure 42: CSTS",
        description="CSTS",
        table=spanned(page(CAPTION_ROW, header, ["260", "M", "FRMW"])),
    )
    later = spanned(page(CAPTION_ROW, header, ["", "", "b"], ["262", "M", "ELPE"]))
    alone = spanned(page(["261", "M", "LPA: a"]))
    assembled(figure, [(381, later), (380, alone)])
    rows = [[c.text for c in r.cells] for r in figure.table.rows[2:]]
    assert rows == [
        ["260", "M", "FRMW"],
        ["261", "M", "LPA: a\nb"],
        ["262", "M", "ELPE"],
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


def test_text_printed_below_the_table_is_no_cell_text():
    columns = Columns(
        [72.0, 300.0],
        [(72.0, 100, 200), (300.0, 100, 200)],
        (80.0, 105.0, 290.0, 195.0),
    )
    # The heading of the next section, tagged into a cell, printed under the table
    assert astray((72.0, 215.0, 250.0, 225.0), columns)
    # The table's own last row, and text beside it, whose columns may be read short
    assert not astray((80.0, 190.0, 200.0, 200.0), columns)
    assert not astray((320.0, 150.0, 400.0, 160.0), columns)
    assert not astray(
        (80.0, 215.0, 200.0, 225.0),
        Columns([72.0], [(72.0, 100, 200)], (80.0, 105.0, 290.0, 195.0)),
    )


def read_marked(tmp_path, content):
    """The text the reader gives the one piece of marked content of a page
    drawing 'content'"""

    path = one_page(
        tmp_path / "turned.pdf", f"/P <</MCID 0>> BDC BT /F1 10 Tf {content} ET EMC"
    )
    with pikepdf.open(path) as pdf, pdfplumber.open(path) as plumb:
        pages = Pages(plumb, {page.objgen: i for i, page in enumerate(pdf.pages)})
        text, _ = pages.text([[Leaf(pdf.pages[0].objgen, 0)]])
    return text


def test_text_turned_to_read_upward_reads_forward(tmp_path):
    # A header turned by 90 degrees, as a narrow column's, its matrix rotating
    assert (
        read_marked(tmp_path, "0 1 -1 0 100 100 Tm (Extended only) Tj")
        == "Extended only"
    )


def test_text_turned_to_read_downward_reads_forward_too(tmp_path):
    assert (
        read_marked(tmp_path, "0 -1 1 0 100 200 Tm (Extended only) Tj")
        == "Extended only"
    )


def test_two_lines_turned_are_read_in_their_order(tmp_path):
    upward = "0 1 -1 0 100 100 Tm (First) Tj 0 1 -1 0 112 100 Tm (Second) Tj"
    assert read_marked(tmp_path, upward) == "First\nSecond"
    downward = "0 -1 1 0 112 200 Tm (First) Tj 0 -1 1 0 100 200 Tm (Second) Tj"
    assert read_marked(tmp_path, downward) == "First\nSecond"


def test_the_outline_places_each_section_on_its_page(tmp_path):
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(300, 400))
    pdf.add_blank_page(page_size=(300, 400))
    with pdf.open_outline() as tree:
        tree.root.append(
            pikepdf.OutlineItem("1 First", 0, "XYZ", left=69, top=350, zoom=0)
        )
        tree.root.append(
            pikepdf.OutlineItem("1.1 Second", 1, "XYZ", left=69, top=100, zoom=0)
        )
        tree.root.append(pikepdf.OutlineItem("Loose"))
    assert outline(pdf) == [
        Section("1", "First", 0, 50.0),
        Section("1.1", "Second", 1, 300.0),
        Section(None, "Loose", None, None),
    ]


def test_a_figure_is_of_the_last_section_the_outline_places_before_it():
    sections = [
        Section("1", "First", 0, 50.0),
        Section("1.1", "Second", 1, 300.0),
        Section(None, "Loose"),
    ]
    assert section_at(sections, 0, 200.0) == sections[0]
    assert section_at(sections, 1, 290.0) == sections[0]
    assert section_at(sections, 1, 300.0) == sections[1]
    assert section_at(sections, 3, 10.0) == sections[1]
    assert section_at([Section("1", "First")], 0, 10.0) is None


def test_a_table_nested_in_a_cell_goes_on_past_the_page_break_too():
    inner = page(["Bits", "Description"], ["31:25", "Reserved"])
    first = spanned(
        page(
            CAPTION_ROW,
            ["Bytes", "Name", "Description"],
            ["99:96", "CTRATT", "Controller Attributes"],
        )
    )
    first.rows[-1].cells[-1].tables.append(inner)
    figure = Figure(
        figure_nr=338, caption="Figure 338: CSTS", description="Identify", table=first
    )
    # The next page: the caption and header again, then the rest of the row, nothing
    # but the rest of the nested table, its header repeated
    rest = page(["", "", ""])
    rest.rows[0].cells[-1].tables.append(
        page(["Bits", "Description"], ["24", "Idle"], ["23:0", "Reserved"])
    )
    following = page(["103:100", "Next", "The next field"])
    joined(
        figure,
        spanned(
            Table(
                rows=page(CAPTION_ROW, ["Bytes", "Name", "Description"]).rows
                + rest.rows
                + following.rows
            )
        ),
    )
    nested = figure.table.rows[2].cells[-1].tables
    assert len(nested) == 1
    assert [c.text for r in nested[0].rows for c in r.cells][::2] == [
        "Bits",
        "31:25",
        "24",
        "23:0",
    ]
    assert [r.cells[0].text for r in figure.table.rows] == [
        "Figure 42: CSTS",
        "Bytes",
        "99:96",
        "103:100",
    ]


def test_a_range_wrapped_inside_its_lower_number_is_made_one():
    assert unwrapped("1795:179\n2") == "1795:1792"
    assert unwrapped("403:40\n0") == "403:400"
    assert unwrapped("7:4\n3") == "7:4\n3"  # Two values, not a wrapped range
    assert unwrapped("31:16\n15:00") == "31:16\n15:00"
    assert unwrapped("Reserved") == "Reserved"


def test_a_published_pdf_names_its_cns_values_by_their_sections(public, tmp_path):
    """The CNS values of the NVM Command Set's Identify name no structure in a
    column; each is named by the title of the section its reference cites"""

    _, path = document_named(public, "NVM Command Set 1.3")
    figures, _ = read(path)
    assert figures.sections["4.1.5.1"].startswith("NVM Command Set Identify Namespace")
    (cns,) = [
        v for v in public.made(path, tmp_path)["values"] if v["kind"] == "cns_values"
    ]
    names = {e["value"]: e["name"] for e in cns["entries"]}
    assert names["00h"] == "NVM Command Set Identify Namespace Data Structure"
    assert names["16h"] == "Namespace Granularity List"
