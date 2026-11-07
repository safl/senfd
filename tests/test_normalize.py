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
