# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

from argparse import Namespace
from pathlib import Path

import docx
from docx.oxml import parse_xml

from senfd.documents.plain import Numbering, numbered, text_of_cell

NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def cell_with(document, *paragraphs):
    """A table of one cell holding 'paragraphs', each a text and the name of
    its style, or None for the default"""

    cell = document.add_table(rows=1, cols=1).cell(0, 0)
    for i, (text, style) in enumerate(paragraphs):
        paragraph = cell.paragraphs[0] if i == 0 else cell.add_paragraph()
        paragraph.text = text
        if style:
            paragraph.style = document.styles[style]
    return cell


def test_a_paragraph_of_a_list_is_led_by_the_label_word_shows():
    document = docx.Document()
    cell = cell_with(
        document,
        ("Notes:", None),
        ("first", "List Number"),
        ("second", "List Number"),
        ("apart", "List Bullet"),
    )
    labels = Numbering(document).labels
    assert text_of_cell(cell, labels) == "Notes:\n1. first\n2. second\n\u2022 apart"
    assert text_of_cell(cell) == "Notes:\nfirst\nsecond\napart"


def test_a_list_goes_on_across_cells_and_another_list_starts_at_one():
    document = docx.Document()
    cell_with(document, ("first", "List Number"))
    later = cell_with(document, ("second", "List Number"), ("other", "List Number 2"))
    assert text_of_cell(later, Numbering(document).labels) == "2. second\n1. other"


def test_a_level_counts_the_levels_above_it_and_starts_over_below_them():
    document = docx.Document()
    numbering = document.part.numbering_part.element
    numbering.insert(
        0,
        parse_xml(
            f'<w:abstractNum {NS} w:abstractNumId="99">'
            '<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/>'
            '<w:lvlText w:val="%1."/></w:lvl>'
            '<w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="lowerLetter"/>'
            '<w:lvlText w:val="%1.%2)"/></w:lvl></w:abstractNum>'
        ),
    )
    numbering.append(
        parse_xml(f'<w:num {NS} w:numId="99"><w:abstractNumId w:val="99"/></w:num>')
    )
    cell = cell_with(document, *((t, None) for t in ("one", "a", "b", "two", "c")))
    for paragraph, level in zip(cell.paragraphs, (0, 1, 1, 0, 1)):
        numPr = paragraph._p.get_or_add_pPr().get_or_add_numPr()
        numPr.get_or_add_numId().val = 99
        numPr.get_or_add_ilvl().val = level
    assert text_of_cell(cell, Numbering(document).labels) == (
        "1. one\n1.a) a\n1.b) b\n2. two\n2.a) c"
    )


def test_a_number_is_written_as_the_format_of_its_level_says():
    assert [numbered(n, "lowerLetter") for n in (1, 26, 27)] == ["a", "z", "aa"]
    assert numbered(4, "upperRoman") == "IV"
    assert numbered(14, "lowerRoman") == "xiv"
    assert numbered(3, "decimal") == "3"


def test_a_docx_gives_the_title_of_each_section(tmp_path):
    """The figure document of the example .docx has every numbered section's
    title, and each figure's section is among them"""

    from senfd.documents.plain import FromDocx

    figures, _ = FromDocx.convert(Path("example") / "example.docx", Namespace())
    assert figures.sections
    for figure in figures.figures:
        if figure.section:
            assert figures.sections[figure.section] == figure.section_title


def test_the_paragraphs_before_a_table_since_its_heading_are_given_by_table():
    """A figure's paragraphs are those of its section before it, as the one
    stating "up to 511 Zone Identifier entries" before ZNS 1.5 Figure 47"""

    from docx.enum.style import WD_STYLE_TYPE

    from senfd.documents.plain import mentioning, paragraphs_before_tables

    document = docx.Document()
    document.styles.add_style("NVMe H1", WD_STYLE_TYPE.PARAGRAPH)
    document.add_paragraph("Of another section, Figure 1.")
    document.add_paragraph("Changed Zone List", style="NVMe H1")
    document.add_paragraph("Up to 511 entries, as defined in Figure 1.")
    document.add_table(rows=1, cols=1).cell(0, 0).text = "Figure 1: Foo"
    document.add_paragraph("After Figure 1, and before Figure 2.")
    document.add_table(rows=1, cols=1).cell(0, 0).text = "Figure 2: Bar"

    before = paragraphs_before_tables(document)
    assert mentioning(before[1], 1) == ["Up to 511 entries, as defined in Figure 1."]
    assert mentioning(before[2], 2) == ["After Figure 1, and before Figure 2."]
