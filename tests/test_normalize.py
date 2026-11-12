# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import json
from argparse import Namespace
from pathlib import Path

import pytest

import senfd.pipeline
from senfd.normalize import (
    CAPTIONS,
    SHAPES,
    normalize_caption,
    normalize_header,
    parse_caption,
    parse_field_description,
    parse_range,
)
from senfd.tables import Cell, Row


@pytest.fixture(scope="module")
def normalized(tmp_path_factory):
    """The normalised figure document of the example, by caption"""

    tmp_path = tmp_path_factory.mktemp("normalized")
    path = Path("example") / "example.docx"
    senfd.pipeline.process(path, tmp_path, Namespace(skip_figures=None))
    (doc,) = tmp_path.glob("*.normalized.figure.document.json")
    document = json.loads(doc.read_text(encoding="utf-8"))
    return document, {f["caption"]: f for f in document["figures"]}


def test_a_caption_dash_is_spaced_and_the_variant_noted():
    assert normalize_caption("Foo – Command Dword 10")[0] == "Foo - Command Dword 10"
    caption, diagnostics = normalize_caption("Foo –Command Dword 10")
    assert caption == "Foo - Command Dword 10"
    assert [d.code for d in diagnostics] == ["caption-dash"]
    assert normalize_caption("Self-test Results")[0] == "Self-test Results"


def test_a_header_is_its_column_whatever_the_synonym_or_footnote():
    assert normalize_header("Definition")[0] == "description"
    assert normalize_header("O/M 1")[0] == "om"
    assert normalize_header("Combined Opcode1")[0] == "opcode"
    assert normalize_header("Reference Section")[0] == "reference"
    assert normalize_header("Factory Default")[0] == "factory_default"


def test_a_range_is_its_bounds_or_its_text():
    rng = parse_range("bits", "31:16")
    assert (rng.upper, rng.lower) == (31, 16)
    assert (parse_range("bytes", "07").upper, parse_range("bytes", "07").lower) == (
        7,
        7,
    )
    formula = parse_range("bytes", "N+3:N")
    assert (formula.text, formula.upper, formula.lower) == ("N+3:N", None, None)
    assert parse_range("bytes", " ") is None


def test_a_field_description_is_its_name_acronym_and_description():
    assert parse_field_description("Foo Count (FCNT): How many.\nMore.") == (
        "Foo Count",
        "FCNT",
        "How many.\nMore.",
    )
    assert parse_field_description("Bar Mode (BMOD)2: How.") == (
        "Bar Mode",
        "BMOD",
        "How.",
    )
    assert parse_field_description("Bar Entry (BE) The entry.") == (
        "Bar Entry",
        "BE",
        "The entry.",
    )
    assert parse_field_description("Reserved") == ("Reserved", None, "")


def test_an_aside_in_parentheses_after_the_acronym_is_of_the_description():
    """As the last entry of NVM 1.3, Figure 41, writes its tags field, with no
    colon between the acronym and an aside the earlier entries put after one"""

    assert parse_field_description("Foo Tags (FT) (i.e., FST and FRT)") == (
        "Foo Tags",
        "FT",
        "(i.e., FST and FRT)",
    )


def test_a_caption_is_parsed_for_its_subject():
    subject = parse_caption("Ding - Command Dword 11 if Foo Mode is set")
    assert (subject.kind, subject.name, subject.lower, subject.condition) == (
        "command_dword",
        "Ding",
        11,
        "Foo Mode is set",
    )
    pair = parse_caption("Ding - Command Dword 2 and Command Dword 3")
    assert (pair.lower, pair.upper) == (2, 3)
    register = parse_caption("Offset 10h: FOOCAP - Foo Capabilities")
    assert (register.kind, register.offset) == ("register", "10h")
    assert parse_caption("Foo Overview").kind == "other"


def test_every_shape_and_caption_kind_has_a_figure_in_the_example(normalized):
    document, _ = normalized

    shapes = {f["shape"] for f in document["figures"]}
    assert {shape for shape, _ in SHAPES} | {"requirement"} <= shapes
    kinds = {f["subject"]["kind"] for f in document["figures"]}
    assert {kind for kind, _ in CAPTIONS} <= kinds


def test_the_variants_of_a_layout_come_out_as_one_form(normalized):
    _, figures = normalized
    figure = figures["Bar Data Structure"]

    assert figure["columns"] == ["bytes", "om", "description"]
    fields = figure["layout"]["fields"]
    assert [(f["range"]["text"], f["name"], f["acronym"]) for f in fields] == [
        ("03:00", "Bar Identifier", "BID"),
        ("07:04", "Reserved", None),
        ("11:08", "Bar Mode", "BMOD"),
        ("N+3:N", "Bar Entry", "BE"),
        ("n/a", "Bar Tail", "BT"),
        ("NOTE 1", "Bar Descriptor 0", None),
        ("NOTE 1", "Bar Descriptor NBD-1", None),
        ("15:12", None, None),
    ]
    # A sentence is a description, not a name
    assert fields[-1]["description"] == "Ignored by the controller"
    # The reserved row is merged across the O/M and Description columns
    assert fields[1]["columns"] == {"om": ""}
    # The range continued in the row below continues the description
    assert fields[2]["description"] == "How bar runs.\n00b: Bar is off."
    # The elision between the descriptors heads nothing
    assert [f["section"] for f in fields] == [None, None] + ["Bar Specific"] * 6
    assert figure["layout"]["notes"] == ["NOTES: 1. Bar identifiers are unique."]


def test_the_columns_of_a_layout_are_matched_by_name_not_position(normalized):
    _, figures = normalized

    fields = figures["Offset 20h: BARCTL - Bar Control"]["layout"]["fields"]
    assert fields[1]["name"] == "Bar Enable"
    assert fields[1]["columns"] == {"reset": "0h", "type": "RW"}


def test_a_nested_bit_table_is_a_layout_of_its_field(normalized):
    _, figures = normalized

    (attributes,) = [
        f
        for f in figures["Foo Statistics Data Structure"]["layout"]["fields"]
        if f["acronym"] == "FATTR"
    ]
    (nested,) = attributes["layouts"]
    assert nested["unit"] == "bits"
    assert [f["acronym"] for f in nested["fields"]] == [None, "FON"]


def test_a_row_spanning_other_grid_columns_than_the_header_is_mapped_by_cells():
    from senfd.documents.normalized import values_of

    grid = ["bytes", "om", "description", "reported", "reported"]
    row = Row(cells=[Cell(text=t) for t in ["15", "O", "Foo (F)", "Yes"]])
    values = values_of(row, grid)
    assert values.texts == {
        "bytes": "15",
        "om": "O",
        "description": "Foo (F)",
        "reported": "Yes",
    }

    heading = Row(cells=[Cell(text="Foo Specific")])
    assert values_of(heading, grid).spans == 1


def test_headers_differing_by_a_number_are_columns_of_their_own(normalized):
    _, figures = normalized

    figure = figures["Supported Foo Operations"]
    assert figure["columns"] == ["command_1", "command_2", "opcode", "command"]
    assert figure["entries"][0]["command_1"] == "Ding"


def test_an_entry_table_has_its_sections_and_notes_and_no_header_again(normalized):
    _, figures = normalized

    figure = figures["Foo Get - Command Specific Status Values, Foo Get"]
    assert [(e["value"], e.get("section")) for e in figure["entries"]] == [
        ("82h", "Foo Errors"),
        ("83h", "Foo Errors"),
    ]
    assert figure["notes"] == ["NOTE: Foo values are few."]


def test_dword_captions_with_a_condition_or_a_qualifier_are_dwords():
    subject = parse_caption("Completion Queue Entry Dword 0 when Foo is set to 1b")
    assert (subject.kind, subject.lower, subject.condition) == (
        "completion_dword",
        0,
        "Foo is set to 1b",
    )
    subject = parse_caption(
        "Foo Set - Command Dword 10 - Foobar Command Set Specific Fields"
    )
    assert (subject.kind, subject.name, subject.lower, subject.qualifier) == (
        "command_dword",
        "Foo Set",
        10,
        "Foobar Command Set Specific Fields",
    )


def test_a_name_ending_in_a_number_keeps_it():
    """Only after an acronym is a number a footnote marker"""

    assert parse_field_description("Entry 1: The first.") == (
        "Entry 1",
        None,
        "The first.",
    )
    assert parse_field_description("Foo NFOO-1: The last.")[0] == "Foo NFOO-1"


def test_a_header_of_two_rows_names_the_columns_below_its_spanning_cell(normalized):
    _, figures = normalized

    figure = figures["Foo Command Support Requirements"]
    assert figure["columns"] == ["command", "opcode", "i_o", "admin"]
    assert figure["entries"] == [
        {"command": "Foo Get", "opcode": "C2h", "i_o": "M", "admin": "O"}
    ]


def rows(*texts):
    return [Row(cells=[Cell(text=t) for t in row]) for row in texts]


def test_irregular_rows_of_a_layout_are_warnings_not_fields():
    from senfd.documents.normalized import parse_layout

    diagnostics = []
    layout = parse_layout(
        rows(
            ("07:00", "M", "Foo (F): Foo.", "x"),
            ("", "O", "Foo text"),
            ("15:08", "O", "Bar (B): Bar."),
        ),
        ["bytes", "om", "description"],
        diagnostics,
    )
    assert [f.acronym for f in layout.fields] == ["B"]
    assert [d.code for d in diagnostics] == ["row-length", "range"]


def test_a_layout_of_names_and_descriptions_has_both():
    from senfd.documents.normalized import parse_layout

    layout = parse_layout(
        rows(("31:00", "Foo Count (FC)", "How many foos.")),
        ["bits", "name", "description"],
        [],
    )
    (field,) = layout.fields
    assert (field.name, field.acronym, field.description) == (
        "Foo Count",
        "FC",
        "How many foos.",
    )


def test_a_table_in_a_cell_that_is_no_layout_is_left_as_text():
    from senfd.documents.normalized import parse_nested
    from senfd.tables import Table

    assert parse_nested(Table(rows=rows(("Foo", "Bar"), ("1", "2"))), []) is None
    assert parse_nested(Table(rows=[]), []) is None


def test_entries_name_their_acronym_and_warn_of_irregular_rows():
    from senfd.documents.normalized import parse_entries

    diagnostics, notes = [], []
    entries = parse_entries(
        rows(("80h", "Foo Busy (FB): Foo is busy."), ("81h",), ("82h", "a", "b")),
        ["value", "description"],
        diagnostics,
        ["Value", "Description"],
        notes,
    )
    assert entries == [
        {
            "value": "80h",
            "description": "Foo is busy.",
            "name": "Foo Busy",
            "acronym": "FB",
        }
    ]
    assert [d.code for d in diagnostics] == ["row-length"]


def test_words_in_parentheses_after_the_name_of_an_entry_are_no_acronym():
    """A table of values says something of a name in parentheses after it, as
    "(Optional)" or "(Admin)"; the name keeps them, and an acronym is only
    what is written as one"""

    from senfd.documents.normalized import parse_entries

    entries = parse_entries(
        rows(
            ("00h", "Foo 0 Doorbell (Admin)"),
            ("04h", "Foo Self Test (Optional)"),
            ("08h", "Foo tag (Foo Tag)"),
            ("0Ch", "Foo Status (FSTS)"),
            ("10h", "Foo Type (Foo-Type)"),
        ),
        ["start", "name"],
        [],
        ["Start", "Name"],
        [],
    )
    assert [(e["name"], e.get("acronym")) for e in entries] == [
        ("Foo 0 Doorbell (Admin)", None),
        ("Foo Self Test (Optional)", None),
        ("Foo tag (Foo Tag)", None),
        ("Foo Status", "FSTS"),
        ("Foo Type", "Foo-Type"),
    ]

    described = parse_entries(
        rows(
            ("0h", "Foo Mode (refer to section 1): The mode."),
            ("1h", "Foo Buffer (Admin): The buffer."),
        ),
        ["value", "description"],
        [],
        ["Value", "Description"],
        [],
    )
    assert described == [
        {
            "value": "0h",
            "name": "Foo Mode (refer to section 1)",
            "description": "The mode.",
        },
        {"value": "1h", "name": "Foo Buffer (Admin)", "description": "The buffer."},
    ]


def test_an_acronym_whose_parenthesis_is_left_open_is_read_and_noted():
    """A row that is "Name (ACRONYM" and nothing more has its name and its
    acronym, and the defect of the document is noted; text that goes on, or
    is cut short in words, is no acronym"""

    from senfd.documents.normalized import parse_layout

    assert parse_field_description("Foo Master Enable (FME") == (
        "Foo Master Enable",
        "FME",
        "",
    )
    assert parse_field_description("Foo Master Enable (refer to")[0] is None
    assert parse_field_description("Foo Master Enable (FME\nIt enables.")[0] is None

    diagnostics = []
    layout = parse_layout(
        rows(("03", "Foo Slave Enable (FSE)"), ("02", "Foo Master Enable (FME")),
        ["bits", "name"],
        diagnostics,
    )
    assert [(f.name, f.acronym) for f in layout.fields] == [
        ("Foo Slave Enable", "FSE"),
        ("Foo Master Enable", "FME"),
    ]
    assert [(d.severity, d.code, d.message) for d in diagnostics] == [
        (
            "note",
            "acronym-open",
            "Field 02 Foo Master Enable: the parenthesis of its acronym 'FME' "
            "is not closed",
        )
    ]


def test_a_header_below_a_title_row_is_found_and_noted():
    from senfd.documents.normalized import normalize_figure
    from senfd.documents.plain import Figure
    from senfd.tables import Table

    figure = Figure(
        figure_nr=1,
        caption="Figure 1: Foo Layout",
        description="Foo Layout",
        table=Table(
            rows=rows(
                ("Figure 1: Foo Layout",),
                ("Foo",),
                ("Bytes", "Description"),
                ("00", "Foo (F)"),
            )
        ),
    )
    diagnostics = []
    normalized = normalize_figure(figure, diagnostics)
    assert normalized.shape == "layout"
    assert [f.acronym for f in normalized.layout.fields] == ["F"]
    assert [d.code for d in diagnostics] == ["header-row"]


def test_a_table_of_no_known_shape_is_entries_by_its_column_names(normalized):
    _, figures = normalized

    flow = figures["RPMB - Foo Write Flow"]
    assert flow["shape"] == "table"
    assert flow["entries"][0]["bytes_in_command"] == "511:00"
    versions = figures[
        "Foobar Command Set Specification Version Descriptor Field Values"
    ]
    assert versions["shape"] == "table"
    assert [e["mjr_field"] for e in versions["entries"]] == ["1h", "1h"]
    properties = figures["Foo Property Definition"]
    assert (properties["entries"][0]["name"], properties["entries"][0]["acronym"]) == (
        "Foo Capabilities",
        "FCAP",
    )


def test_a_figure_has_its_page_and_section(normalized):
    """The section by counting the headings, which Word numbers, and by the
    table of contents where it numbers a section otherwise"""

    _, figures = normalized
    ding = figures["Ding - Command Dword 10"]
    assert (ding["page_nr"], ding["section"], ding["section_title"]) == (
        2,
        "1.2",
        "Ding command",
    )
    assert figures["Foo Statistics Data Structure"]["section"] == "4"


def test_tables_written_oddly_are_the_figures_they_caption(normalized):
    """The number of the figure a field of Word, the caption after an empty
    cell, the table wrapped in another, and the next figure's caption and
    rows in the table of this one"""

    _, figures = normalized
    for caption, acronym in [
        ("Foo Numbered Layout", "FNUM"),
        ("Foo Indented Layout", "FIND"),
        ("Foo Wrapped Layout", "FWRP"),
        ("Foo Joined Layout", "FFST"),
        ("Foo Joining Layout", "FSND"),
    ]:
        fields = figures[caption]["layout"]["fields"]
        assert [f["acronym"] for f in fields] == [acronym], caption


def test_a_hyphen_that_does_not_break_is_a_hyphen(normalized):
    _, figures = normalized

    (field,) = figures["Foo Numbered Layout"]["layout"]["fields"]
    assert field["name"] == "Foo-Bar Number"


def test_the_normalising_module_is_imported_on_its_own():
    """As a script or a test of it would, with nothing of senfd imported before"""

    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "-c", "import senfd.normalize"], capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stderr


def test_a_name_holding_a_range_in_brackets_keeps_its_colon():
    from senfd.normalize import parse_field_description

    assert parse_field_description("KV Key[63:00]: The least-significant 64 bits.") == (
        "KV Key[63:00]",
        None,
        "The least-significant 64 bits.",
    )
    assert parse_field_description("Key[127:64] (KVK): The rest.") == (
        "Key[127:64]",
        "KVK",
        "The rest.",
    )
    assert parse_field_description("Name (ACR): A description: with a colon.") == (
        "Name",
        "ACR",
        "A description: with a colon.",
    )


def test_a_row_of_conditions_over_the_ranges_heads_them_and_is_no_field():
    """As "HDGSTF=1" and "HDGSTF=0" of NVMe over TCP 1.3, over the bytes of
    the header digest when it is present and when it is not"""

    from senfd.documents.normalized import parse_layout

    diagnostics = []
    layout = parse_layout(
        rows(
            ("HDGSTF=1", "HDGSTF=0", ""),
            ("75:72", "Not present", "PDU Header Digest (HDGST): The digest."),
        ),
        ["bytes", "bytes", "description"],
        diagnostics,
    )
    assert [(f.range.text, f.acronym) for f in layout.fields] == [("75:72", "HDGST")]
    assert [d.code for d in diagnostics] == ["range-condition"]


def test_a_name_wrapped_by_a_narrow_column_is_one_name():
    """As Base 2.4's nested bit tables, where the acronym falls on the next
    line of the first paragraph"""

    assert parse_field_description(
        "Sanitize Media Verification Event Support\n(SMVES)"
    ) == ("Sanitize Media Verification Event Support", "SMVES", "")
    assert parse_field_description(
        "Predictable Latency Event\nAggregate (PLEAN): If set.\nMore."
    ) == ("Predictable Latency Event Aggregate", "PLEAN", "If set.\nMore.")
    assert parse_field_description("Reserved\nFoo (F): not a wrap.")[0] == "Reserved"
    assert (
        parse_field_description("Foo bar baz qux quux\nsee (refer to Figure 3)")[1]
        is None
    )


def diagram_of_bytes(*rows):
    """A figure of a diagram of bytes by their bits, its rows as the reader
    of a PDF gives them: of as many cells as the row has borders for"""

    from senfd.documents.plain import Figure
    from senfd.tables import Table

    caption = "Figure 1: Foo Guard Format"
    head = [
        Row(cells=[Cell(text=caption)]),
        Row(
            cells=[
                Cell(text=caption, merged="up"),
                *[Cell(text=t) for t in ("", "Bit", "")],
            ]
        ),
        Row(
            cells=[
                Cell(text=caption, merged="up"),
                *[Cell(text=t) for t in " 76543210 "],
            ]
        ),
    ]
    body = [Row(cells=[Cell(text=t) for t in row]) for row in rows]
    return Figure(
        figure_nr=1,
        caption=caption,
        description="Foo Guard Format",
        table=Table(rows=[row for row in head + body]),
    )


def test_a_diagram_of_bytes_by_their_bits_is_a_layout_of_the_fields_it_delimits():
    """As the protection information formats are drawn: the bits 7 to 0
    across, a row for each byte, and each field from the row marked MSB to
    the row marked LSB"""

    from senfd.documents.normalized import normalize_figure

    diagnostics = []
    normalized = normalize_figure(
        diagram_of_bytes(
            ("Byte", "0", "MSB", "Foo Guard", "", ""),
            ("1", "", "LSB", "", "", ""),
            ("2", "MSB", "Foo Tag", "", "", ""),
            ("3", "", "", "", "", ""),
            ("4", "", "LSB", "", "", ""),
        ),
        diagnostics,
    )

    assert (normalized.shape, normalized.layout.unit) == ("layout", "bytes")
    assert [
        (f.range.text, f.range.upper, f.range.lower, f.name, f.columns)
        for f in normalized.layout.fields
    ] == [
        ("1:0", 1, 0, "Foo Guard", {"msb_byte": "0", "lsb_byte": "1"}),
        ("4:2", 4, 2, "Foo Tag", {"msb_byte": "2", "lsb_byte": "4"}),
    ]
    assert [d.code for d in diagnostics] == ["byte-diagram"]


@pytest.mark.parametrize(
    "rows",
    [
        # A byte after the last LSB, of no field
        [("Byte", "0", "MSB", "Foo Guard", "LSB"), ("1", "", "")],
        # A field that is not closed by an LSB
        [("Byte", "0", "MSB", "Foo Guard", ""), ("1", "", "")],
        # Two names between an MSB and its LSB
        [("Byte", "0", "MSB", "Foo Guard", ""), ("1", "Foo Tag", "LSB")],
        # Bytes that are not numbered from 0, each the next
        [("Byte", "0", "MSB", "Foo Guard", ""), ("2", "", "LSB")],
    ],
)
def test_a_diagram_with_a_byte_that_no_field_is_delimited_for_is_no_layout(rows):
    from senfd.documents.normalized import normalize_figure

    assert normalize_figure(diagram_of_bytes(*rows), []).layout is None
