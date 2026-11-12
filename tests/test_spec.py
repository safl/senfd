# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import json
import runpy
from argparse import Namespace
from pathlib import Path

import pytest

import senfd.pipeline
from senfd.documents.spec import SpecDocument, merge

OPCODES = ("Function", "Data Transfer", "Combined Opcode", "Command", "Reference")


def spec_of(path, tmp_path):
    """The specification document senfd makes of the document at 'path'"""

    tmp_path.mkdir(parents=True, exist_ok=True)
    senfd.pipeline.process(path, tmp_path, Namespace(skip_figures=None))
    (spec,) = tmp_path.glob(f"{path.stem}.spec.document.json")
    return SpecDocument.model_validate_json(spec.read_text(encoding="utf-8"))


def other_document(tmp_path, rows):
    """A document of an opcode table of the "Bar" command set of 'rows'"""

    toolbox = runpy.run_path("toolbox/example_docx.py")
    path = tmp_path / "docx" / "other.docx"
    path.parent.mkdir(exist_ok=True)
    caption = "Opcodes for Bar Command Set Commands"
    toolbox["write"](path, [(caption, {"header": OPCODES, "rows": rows})])
    return path


def test_a_command_has_its_dwords_pointers_and_conditions(tmp_path):
    spec = spec_of(Path("example") / "example.docx", tmp_path)
    ding = spec.command_sets["foobar"].commands["ding"]

    assert ding.opcode == 0x01
    assert sorted((d.lower, d.upper, d.condition) for d in ding.sqe) == [
        (2, 3, None),
        (4, 5, None),
        (6, 9, None),
        (10, 10, None),
        (11, 11, "Foo Mode is set"),
        (14, 15, None),
    ]
    (cdw10,) = [d for d in ding.sqe if d.lower == 10]
    assert [(f.acronym, f.upper, f.lower) for f in cdw10.fields] == [
        (None, 31, 16),
        ("FCNT", 15, 0),
    ]
    assert cdw10.source.figure_nr == 2
    assert [(d.lower, d.fields[0].acronym) for d in ding.cqe] == [(0, "FRES")]


def test_a_command_name_is_without_its_footnote_marker(tmp_path):
    spec = spec_of(Path("example") / "example.docx", tmp_path)

    ring = spec.command_sets["foobar"].commands["ring"]
    assert ring.name == "Ring"
    assert 10 in [d.lower for d in ring.sqe]


def test_a_feature_has_the_dwords_its_caption_names_it_by(tmp_path):
    spec = merge([spec_of(Path("example") / "example.docx", tmp_path)])

    feature = spec.features["foo_config"]
    assert feature.identifier == 0xC0
    assert [(d.lower, d.fields[1].acronym) for d in feature.sqe] == [(11, "FLVL")]


def test_a_log_page_has_its_identifier_and_its_structure(tmp_path):
    spec = merge([spec_of(Path("example") / "example.docx", tmp_path)])

    log_page = spec.log_pages["foo_statistics"]
    assert log_page.identifier == 0xC0
    assert log_page.structure.source.figure_nr is not None
    assert spec.log_pages["foo_events"].structure is None
    # A log page of a scope is laid out by the structure of the log page
    scoped = spec.log_pages["foo_statistics_namespace_scope"]
    assert scoped.structure.name == "Foo Statistics"


def test_a_command_gets_the_dwords_another_document_describes(tmp_path):
    example = spec_of(Path("example") / "example.docx", tmp_path / "a")
    other = spec_of(
        other_document(tmp_path, [("0000 00b", "01b", "81h", "Zap", "2.1")]),
        tmp_path / "b",
    )

    merged = merge([example, other])
    zap = merged.command_sets["bar"].commands["zap"]
    assert [(d.lower, d.fields[0].acronym) for d in zap.sqe] == [(10, "ZCNT")]
    assert "zap" not in merged.unassigned


def test_a_command_of_two_command_sets_has_the_dwords_of_both(tmp_path):
    """The same name in two command sets is the same command, as the base
    specification describes commands that a command set lists"""

    example = spec_of(Path("example") / "example.docx", tmp_path / "a")
    other = spec_of(
        other_document(tmp_path, [("0000 00b", "01b", "81h", "Ding", "2.1")]),
        tmp_path / "b",
    )

    merged = merge([example, other])
    bar_ding = merged.command_sets["bar"].commands["ding"]
    assert bar_ding.opcode == 0x81
    assert len(bar_ding.sqe) == len(merged.command_sets["foobar"].commands["ding"].sqe)


def test_dwords_of_no_command_are_a_diagnostic(tmp_path):
    spec = merge([spec_of(Path("example") / "example.docx", tmp_path)])

    said = [d.message for d in spec.diagnostics if d.code == "dwords-unassigned"]
    assert "example, 1.2, Figure 21, page 21: dwords 10:10 of zap, of no command" in (
        "\n".join(said)
    )
    assert "zap" in spec.unassigned


def test_the_merged_specification_is_written_by_the_command_line(tmp_path, monkeypatch):
    import senfd.cli

    docs = sorted(Path("example").glob("*.docx"))
    monkeypatch.setattr(
        "sys.argv", ["senfd", *map(str, docs), "--output", str(tmp_path)]
    )
    assert senfd.cli.main() == 0
    merged = json.loads(
        (tmp_path / "merged.spec.document.json").read_text(encoding="utf-8")
    )
    assert "foobar" in merged["command_sets"]


def test_a_directive_operation_is_an_operation_of_its_command(tmp_path):
    spec = merge([spec_of(Path("example") / "example.docx", tmp_path)])
    commands = spec.command_sets["admin"].commands

    (reset,) = commands["foo_directive_send"].operations
    assert (reset.name, reset.selectors) == ("Bar Reset", {"DTYPE": 1, "DOPER": 1})
    assert [(d.lower, d.fields[1].acronym) for d in reset.sqe] == [(12, "BRC")]

    (report,) = commands["foo_directive_receive"].operations
    assert report.structures == ["Bar Directive - Bar Report"]
    assert "bar_reset" not in spec.unassigned


def test_a_document_on_its_own_has_its_features_log_pages_and_diagnostics(tmp_path):
    spec = spec_of(Path("example") / "example.docx", tmp_path)

    assert spec.features["foo_config"].sqe
    assert spec.log_pages["foo_statistics"].structure
    assert any(d.code == "dwords-unassigned" for d in spec.diagnostics)


def test_a_merge_leaves_the_documents_it_merges_as_they_are(tmp_path):
    example = spec_of(Path("example") / "example.docx", tmp_path / "a")
    other = spec_of(
        other_document(tmp_path, [("0000 00b", "01b", "81h", "Zap", "2.1")]),
        tmp_path / "b",
    )
    before = (example.model_dump(), other.model_dump())

    merge([example, other])
    assert (example.model_dump(), other.model_dump()) == before


def test_two_figures_of_the_same_dwords_are_both_kept(tmp_path):
    """As the base specification and a command set specification both
    describe a dword of a command"""

    example = spec_of(Path("example") / "example.docx", tmp_path / "a")
    twice = example.model_copy(deep=True)
    twice.meta.stem = "again"
    for described in twice.dwords.values():
        for dwords in described:
            dwords.source.document = "again"

    merged = merge([example, twice])
    ding = merged.command_sets["foobar"].commands["ding"]
    assert sorted({d.source.document for d in ding.sqe if d.lower == 10}) == [
        "again",
        "example",
    ]


def test_a_caption_names_a_thing_by_its_name_initials_or_a_longer_name():
    from senfd.documents.spec import log_page_key, names_match

    assert names_match("HCTM", "Host Controlled Thermal Management")
    assert names_match("Arbitration & Command Processing", "Arbitration")
    assert not names_match("Foo", "Foo Config")
    assert names_match("FDP Events", "Flexible Data Placement Events")
    assert names_match("Key Value Config", "Key Value Configuration")
    assert not names_match("Key Value", "Key Value Configuration")
    assert log_page_key("Get Log Page - Foo Discovery Log Page") == "foo_discovery"
    assert log_page_key("Foo Information Log Entry") == "foo_information"
    assert log_page_key("Foo (Controller scope)") == "foo"


def test_values_that_are_not_what_they_must_be_are_errata_not_model(tmp_path):
    spec = merge([spec_of(Path("example") / "example.docx", tmp_path)])
    ring = spec.command_sets["foobar"].commands["ring"]

    errata = {(e.code, e.found) for e in spec.errata}
    assert ("range-outside", "64:00") in errata
    assert ("acronym", "R MODE") in errata
    assert ("opcode", "x") in errata
    assert ("gap", ", ".join(str(b) for b in range(8))) in errata
    assert not [e for e in spec.errata if e.found == "80h to FFh"]

    # The field beyond its dwords is not in the model, the bad acronym is not
    (cdw14,) = [d for d in ring.sqe if d.lower == 14]
    assert cdw14.fields == []
    (cdw11,) = [d for d in ring.sqe if d.lower == 11]
    assert [(f.name, f.acronym) for f in cdw11.fields] == [("Ring Mode", None)]
    assert "zing" not in spec.command_sets["foobar"].commands

    # The bits the left out field had are its erratum, not a gap besides
    assert not [e for e in spec.errata if e.code == "gap" and "cdw14" in e.message]


def test_the_values_of_a_table_are_typed(tmp_path):
    spec = spec_of(Path("example") / "example.docx", tmp_path)
    (requirements,) = [v for v in spec.values if v.name == "Foo Feature"]
    by_name = {e.name or e.value: e for e in requirements.entries}

    mode = by_name["Foo Mode"]
    assert (mode.typed["identifier"].lower, mode.typed["identifier"].upper) == (
        0xC1,
        0xC3,
    )
    assert (mode.typed["i_o"].level, mode.typed["i_o"].footnotes) == ("M", [2])
    assert mode.typed["admin"].note == 3
    assert mode.typed["discovery"].reference == "Bar Specification"
    spare = by_name["Foo Spare"]
    assert (spare.typed["identifier"].lower, spare.typed["identifier"].upper) == (
        0xC4,
        0xC7,
    )
    assert [spare.typed[c].kind for c in ("i_o", "admin")] == [
        "reserved",
        "vendor_specific",
    ]

    (cns,) = [v for v in spec.values if v.kind == "cns_values"]
    assert cns.entries[0].typed["nsid"].flag is True

    # A value of no form its column holds is an erratum, and is not typed
    assert ("value", "Maybe") in {(e.code, e.found) for e in spec.errata}
    assert "i_o" not in by_name["Foo Odd"].typed


def test_fields_sharing_bytes_are_the_alternatives_of_a_union(tmp_path):
    spec = spec_of(Path("example") / "example.docx", tmp_path)
    (address,) = [st for st in spec.structures if st.name == "Foo Address"]

    assert [(f.range, f.union, f.alternative) for f in address.fields] == [
        ("00", None, None),
        ("01:01", None, None),
        ("17:02", 0, 0),
        ("05:02", 0, 1),
        ("17:06", 0, 1),
    ]


def test_a_field_s_values_select_the_operations_of_its_command(tmp_path):
    spec = merge([spec_of(Path("example") / "example.docx", tmp_path)])
    migrate = spec.command_sets["foobar"].commands["foo_migrate"]

    (cdw10,) = [d for d in migrate.sqe if d.lower == 10]
    select = cdw10.fields[1]
    assert [
        (v.value, v.typed["value"].lower, v.columns["om"]) for v in select.values
    ] == [
        ("0h", 0, "M"),
        ("1h", 1, "O"),
        ("2h", 2, "O"),
    ]
    assert [
        (o.name, o.selectors, [f.acronym for d in o.sqe for f in d.fields])
        for o in migrate.operations
    ] == [("Foo Pause", {"SEL": 0}, ["FPT"]), ("Foo Go", {"SEL": 1}, ["FGS"])]

    # The dwords of the command Ding are no operation of Foo Migrate
    assert spec.command_sets["foobar"].commands["ding"].sqe


def test_a_field_s_values_are_typed_by_a_value_column_named_after_it(tmp_path):
    spec = spec_of(Path("example") / "example.docx", tmp_path)
    migrate = spec.command_sets["foobar"].commands["foo_migrate"]

    (cdw12,) = [d for d in migrate.sqe if d.lower == 12]
    values = cdw12.fields[1].values
    assert [
        (v.value, v.typed["value"].lower, v.typed["value"].upper) for v in values
    ] == [
        ("000b", 0, 0),
        ("001b", 1, 1),
        ("010b to 111b", 2, 7),
    ]

    # The heading the values are under names none of them
    (cdw10,) = [d for d in migrate.sqe if d.lower == 10]
    assert "Foo Operations" not in [o.name for o in migrate.operations]


def test_fields_of_several_structures_in_a_table_are_no_union(tmp_path):
    spec = spec_of(Path("example") / "example.docx", tmp_path)
    (sizes,) = [st for st in spec.structures if st.name == "Foo Size Fields"]
    assert [f.union for f in sizes.fields] == [None, None]


def test_a_layout_of_bytes_and_bits_nests_the_bits_in_their_byte_range(tmp_path):
    """A header of bytes and bits, each byte range named by the heading row
    above it and merged down over a row for each range of its bits"""

    spec = spec_of(Path("example") / "example.docx", tmp_path)
    (baz,) = [st for st in spec.structures if st.name == "Baz Capabilities"]
    assert baz.unit == "bytes"
    assert [(f.range, f.name, f.unit, f.section) for f in baz.fields] == [
        ("31:00", "Baz Supported", "bytes", None),
        ("63:32", "Baz Enabled", "bytes", None),
        ("4095:64", "Reserved", "bytes", None),
    ]
    assert [[(b.range, b.acronym, b.unit) for b in f.fields] for f in baz.fields] == [
        [("255:02", None, "bits"), ("01", "ZS", "bits"), ("00", "RS", "bits")],
        [("255:02", None, "bits"), ("01", "ZE", "bits"), ("00", "RE", "bits")],
        [],
    ]


def test_the_unions_of_a_layout_and_those_nested_in_it_have_numbers_of_their_own():
    from senfd.documents.spec import ReadBits as Bits, number_unions

    def bits(range_, union, fields=()):
        return Bits(
            unit="bits", range=range_, union=union, alternative=0, fields=list(fields)
        )

    nested = [bits("1:0", 0), bits("1:0", 0)]
    fields = [bits("7:0", 0), bits("7:0", 0, nested)]
    number_unions(fields)
    assert [f.union for f in fields] == [0, 0]
    assert [f.union for f in nested] == [1, 1]


OPERATIONS = [
    ("heading", 1, "Alpha command"),
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
            "rows": [
                ("0000 00b", "01b", "81h", "Alpha", "1"),
                ("0000 01b", "01b", "82h", "Beta", "2"),
            ],
        },
    ),
    (
        "Alpha - Command Dword 10",
        {
            "header": ("Bits", "Description"),
            "rows": [
                (
                    "07:00",
                    (
                        "Select (SEL): The operation.",
                        {"header": ("Value", "Operation"), "rows": [("0h", "Create")]},
                    ),
                ),
            ],
        },
    ),
    ("heading", 2, "Create (Management Operation 0h)"),
    (
        "Create - Command Dword 11",
        {"header": ("Bits", "Description"), "rows": [("31:00", "Alpha Count (ACNT)")]},
    ),
    (
        "Make - Command Dword 12",
        {"header": ("Bits", "Description"), "rows": [("31:00", "Alpha Make (AMK)")]},
    ),
    ("heading", 1, "Beta command"),
    (
        "Beta - Command Dword 10",
        {
            "header": ("Bits", "Description"),
            "rows": [
                (
                    "07:00",
                    (
                        "Select (SEL): The operation.",
                        {"header": ("Value", "Operation"), "rows": [("0h", "Create")]},
                    ),
                ),
            ],
        },
    ),
]


def test_an_operation_takes_the_dwords_of_its_own_command_s_section(tmp_path):
    """Two commands each have a Create; the dwords are of the one whose
    section they are in, the order of the opcode table whatever, and dwords
    a section names after the operation are of it too"""

    toolbox = runpy.run_path("toolbox/example_docx.py")
    for order in (0, 1):
        figures = [list(f) if isinstance(f, tuple) else f for f in OPERATIONS]
        rows = OPERATIONS[1][1]["rows"]
        table = dict(OPERATIONS[1][1], rows=rows if order == 0 else rows[::-1])
        figures[1] = (OPERATIONS[1][0], table)
        path = tmp_path / f"order{order}" / "operations.docx"
        path.parent.mkdir()
        toolbox["write"](path, [tuple(f) for f in figures])
        spec = merge([spec_of(path, tmp_path / f"out{order}")])
        commands = spec.command_sets["bar"].commands

        (create,) = commands["alpha"].operations
        assert [(d.lower, d.fields[0].acronym) for d in create.sqe] == [
            (11, "ACNT"),
            (12, "AMK"),
        ]
        assert commands["beta"].operations == []


def test_an_operation_takes_no_dwords_of_another_document(tmp_path):
    example = spec_of(Path("example") / "example.docx", tmp_path / "a")
    toolbox = runpy.run_path("toolbox/example_docx.py")
    path = tmp_path / "docx" / "other.docx"
    path.parent.mkdir()
    toolbox["write"](
        path,
        [
            (
                "Foo Pause - Command Dword 12",
                {"header": ("Bits", "Description"), "rows": [("31:00", "Other (OTH)")]},
            )
        ],
    )
    merged = merge([example, spec_of(path, tmp_path / "b")])
    migrate = merged.command_sets["foobar"].commands["foo_migrate"]

    (pause,) = [o for o in migrate.operations if o.name == "Foo Pause"]
    assert [d.lower for d in pause.sqe] == [11]


def test_a_register_of_a_format_it_shares_is_named_by_its_section(tmp_path):
    spec = spec_of(Path("example") / "example.docx", tmp_path)
    (version,) = [st for st in spec.structures if st.name == "FOOVER - Foo Version"]

    assert (version.kind, version.offset) == ("register", "18h")
    assert [f.acronym for f in version.fields] == ["FMJR", "FMNR"]


def test_a_table_of_values_keeps_the_scope_its_caption_confines_it_to(tmp_path):
    spec = spec_of(Path("example") / "example.docx", tmp_path)
    scoped = [
        (v.qualifier, v.scope)
        for v in spec.values
        if v.kind == "status_values" and v.qualifier == "Generic Command"
    ]

    assert ("Generic Command", "Foo Commands") in scoped
    assert ("Generic Command", "Foobar Command Set") in scoped


def test_fields_named_by_their_index_keep_their_offsets_with_rows_left_out(
    tmp_path,
):
    spec = spec_of(Path("example") / "example.docx", tmp_path)
    (table,) = [st for st in spec.structures if st.name == "Foo Table"]
    (results,) = [st for st in spec.structures if st.name == "Foo Results"]

    assert [(f.name, f.lower, f.upper) for f in table.fields][:3] == [
        ("Foo Slot 0 Descriptor", 0, 31),
        ("Foo Slot 1 Descriptor", 32, 63),
        ("Foo Slot 7 Descriptor", 224, 255),
    ]
    assert [f.acronym for f in results.fields] == ["FRC", "FFL", "FR1", "FR2", "FR5"]


def test_a_range_of_identifiers_may_give_the_h_once():
    typed = senfd.documents.spec.typed_of("86 to BFh")
    assert (typed.kind, typed.lower, typed.upper) == ("identifier", 0x86, 0xBF)


@pytest.mark.parametrize(
    "text, footnotes",
    [("n/a", []), ("N/A 2", [2]), ("n/a9", [9]), ("Not Applicable", [])],
)
def test_a_value_left_not_applicable_is_said_so_with_its_footnotes(text, footnotes):
    typed = senfd.documents.spec.typed_of(text)
    assert (typed.kind, typed.footnotes) == ("not_applicable", footnotes)


def test_a_column_of_flags_may_leave_a_row_not_applicable():
    """As Base 2.4, Figure 466, where a footnote marks "n/a"; and a value of no
    form the column holds stays an erratum"""

    values = senfd.documents.spec.Values(
        kind="requirements",
        columns=["field", "persistent"],
        entries=[
            senfd.documents.spec.Entry(
                value=field,
                value_column="field",
                name=field,
                columns={"persistent": said},
            )
            for field, said in (("F0", "Yes"), ("F1", "n/a9"), ("F2", "Maybe"))
        ],
        source=senfd.documents.spec.Source(document="example", figure_nr=1),
    )
    errata = senfd.documents.spec.type_values(values)
    assert [e.found for e in errata] == ["Maybe"]
    typed = values.entries[1].typed["persistent"]
    assert (typed.kind, typed.footnotes) == ("not_applicable", [9])


def test_a_column_of_sentences_is_text_whatever_its_name():
    values = senfd.documents.spec.Values(
        kind="requirements",
        columns=["field", "size_requirement"],
        entries=[
            senfd.documents.spec.Entry(
                value=f"F{n}",
                value_column="field",
                columns={"size_requirement": "The bytes of the output of the hash"},
            )
            for n in range(3)
        ],
        source=senfd.documents.spec.Source(document="example", figure_nr=1),
    )
    assert senfd.documents.spec.type_values(values) == []


def test_bits_beyond_the_bytes_holding_them_are_a_candidate_erratum():
    """A field of one byte whose nested bits run to bit 15, as "15:3 Reserved"
    under byte 362 of Base 2.4's Identify Controller"""

    from senfd.documents.spec import ReadBits as Bits, Source, checked

    source = Source(document="example", figure_nr=338)
    byte = Bits(
        unit="bytes",
        upper=362,
        lower=362,
        range="362",
        name="Restore Attributes",
        fields=[
            Bits(unit="bits", upper=15, lower=3, range="15:3", name="Reserved"),
            Bits(unit="bits", upper=2, lower=0, range="2:0", name="Supported"),
        ],
    )
    wide = byte.model_copy(update={"upper": 363, "range": "363:362"})
    kept, errata, _ = checked([byte, wide], None, source)
    assert [(e.code, e.found, e.message) for e in errata] == [
        (
            "range-outside",
            "15:3",
            "Field 15:3 Reserved: bit 15 beyond the 8 bits of byte 362",
        )
    ]
    assert [f.range for f in kept[0].fields] == ["2:0"]
    assert [f.range for f in kept[1].fields] == ["15:3", "2:0"]


def test_a_range_is_typed_and_text_that_is_none_is_a_candidate_erratum():
    """As "(NUMENT-1)*32+63)" of Base 2.4, Figure 361, closing a parenthesis
    it never opened, and "4*(N+1)+3: 4 * (N+4)" of Figure 404, whose upper
    bound is below its lower whatever N is"""

    from senfd.documents.spec import ReadBits as Bits, Source, checked

    source = Source(document="example", figure_nr=361)
    fields = [
        Bits(unit="bytes", range="(n*32)-1:(n-1)*32", name="Entry"),
        Bits(unit="bytes", range="n/a", name="Open"),
        Bits(unit="bytes", range="(NUMENT-1)*32+63): ((NUMENT-1)*32+32)", name="Last"),
        Bits(unit="bytes", range="4*(N+1)+3: 4 * (N+4)", name="Exported"),
    ]
    kept, errata, _ = checked(fields, None, source)
    assert [(f.name, f.kind, f.formula, f.width) for f in kept] == [
        ("Entry", "formula", "32*n - 1:32*n - 32", 32),
        ("Open", "open", None, None),
    ]
    assert [(e.code, e.message) for e in errata] == [
        (
            "range",
            "Field (NUMENT-1)*32+63): ((NUMENT-1)*32+32) Last: "
            "'(NUMENT-1)*32+63)' has ')' after a whole value",
        ),
        (
            "range-reversed",
            "Field 4*(N+1)+3: 4 * (N+4) Exported: upper bound below the lower",
        ),
    ]


def test_bits_nested_in_a_formula_of_bytes_lie_within_its_width():
    from senfd.documents.spec import ReadBits as Bits, Source, checked

    entry = Bits(
        unit="bytes",
        range="(n*2)+1:(n*2)",
        name="Entry",
        fields=[Bits(unit="bits", range="16:00", name="Wide")],
    )
    kept, errata, _ = checked([entry], None, Source(document="example", figure_nr=1))
    assert [e.message for e in errata] == [
        "Field 16:00 Wide: bit 16 beyond the 16 bits of bytes (n*2)+1:(n*2)"
    ]
    assert kept[0].fields == []


def test_bytes_of_no_field_between_two_fields_are_a_gap_unless_rows_are_left_out():
    """As Identify Controller lists Power State Descriptors 0 to 2, then
    "...", then 31; a table of bits lists the highest first"""

    from senfd.documents.spec import Bits, Source, uncovered

    source = Source(document="example", figure_nr=338)

    def span(rng, name, elided=False):
        upper, _, lower = rng.partition(":")
        return Bits(
            unit="bytes",
            range=rng,
            name=name,
            role="field",
            kind="span",
            upper=int(upper),
            lower=int(lower or upper),
            width=int(upper) - int(lower or upper) + 1,
            elided=elided,
        )

    entries = [span("31:00", "Entry 0"), span("63:32", "Entry 1")]
    left_out = entries + [span("127:96", "Entry 3", elided=True)]
    assert uncovered(left_out, "bytes", source) == []
    formula = Bits(
        unit="bytes",
        range="N+3:N",
        role="field",
        kind="formula",
        formula="N + 3:N",
        name="Entry N",
    )
    assert (
        uncovered(entries + [formula, span("199:196", "Last")], "bytes", source) == []
    )

    (gap,) = uncovered(entries + [span("127:96", "Entry 3")], "bytes", source)
    assert (gap.code, gap.message) == (
        "layout-gap",
        "Bytes 64 to 95 are of no field, before 127:96 Entry 3",
    )
    highest_first = [span("31:16", "High"), span("15:14", "Mid", elided=True)]
    assert uncovered(highest_first + [span("07:00", "Low")], "bits", source)[
        0
    ].message == ("Bits 8 to 13 are of no field, before 15:14 Mid")
    assert (
        uncovered([span("31:16", "High"), span("15:14", "Mid")], "bits", source) == []
    )
    (one,) = uncovered([span("00", "A"), span("02", "B")], "bytes", source)
    assert one.message == "Byte 1 is of no field, before 02 B"
    # Fields sharing bytes, as alternatives, leave none
    union = [span("15:00", "IPv6"), span("03:00", "IPv4"), span("31:16", "Port")]
    assert uncovered(union, "bytes", source) == []


def test_a_field_is_made_with_what_it_needs_or_is_left_out():
    """A name, or the place it holds; a row giving neither makes no field"""

    from senfd.documents.spec import ReadBits as Bits, Source, checked

    source = Source(document="example", figure_nr=49)

    def bytes_of(rng, name=None, description=""):
        return Bits(unit="bytes", range=rng, name=name, description=description)

    kept, errata, unnamed = checked(
        [
            bytes_of("03:00", "Foo"),
            bytes_of("07:04", description="Reserved for future use."),
            bytes_of("11:08", description="Most significant 16 bits of the LBST"),
            bytes_of("n/a", description="These bytes have no equivalent."),
            bytes_of("15:12", description="Bus Master Enable (BME"),
        ],
        None,
        source,
    )
    assert [(f.name, f.role, f.description) for f in kept] == [
        ("Foo", "field", ""),
        ("Reserved", "reserved", "Reserved for future use."),
        ("Most significant 16 bits of the LBST", "field", ""),
    ]
    assert errata == []
    assert unnamed == [
        "Field n/a: no name in 'These bytes have no equivalent.'",
        "Field 15:12: no name in 'Bus Master Enable (BME'",
    ]


def test_only_a_figure_laying_out_the_whole_of_something_must_cover_it(tmp_path):
    """A figure of some fields, as those a reference value is given for, is
    of the kind "other" by its caption, and leaves the rest out on purpose"""

    from senfd.documents.normalized import Layout, LayoutField, NormalizedFigure
    from senfd.documents.spec import add_figure
    from senfd.normalize import Subject, parse_range

    def errata_of(kind):
        fields = [
            LayoutField(range=parse_range("bytes", "05:02"), name="NMR"),
            LayoutField(range=parse_range("bytes", "31:16"), name="Reserved"),
        ]
        figure = NormalizedFigure(
            figure_nr=33,
            caption="Foo",
            subject=Subject(kind=kind, name="Foo"),
            layout=Layout(unit="bytes", fields=fields),
        )
        document = SpecDocument()
        add_figure(document, figure, "example")
        return [(e.code, e.message) for e in document.errata]

    assert errata_of("data_structure") == [
        ("layout-gap", "Bytes 6 to 15 are of no field, before 31:16 Reserved")
    ]
    assert errata_of("other") == []


def test_an_acronym_left_open_is_the_fields_and_a_candidate_erratum(tmp_path):
    """The field has the acronym the document means, and the authors are told
    of the parenthesis that is not closed"""

    toolbox = runpy.run_path("toolbox/example_docx.py")
    path = tmp_path / "docx" / "open.docx"
    path.parent.mkdir()
    table = {
        "header": ("Bits", "Name"),
        "rows": [("03", "Foo Slave Enable (FSE)"), ("02", "Foo Master Enable (FME")],
    }
    toolbox["write"](path, [("Offset 04h: FOO - Foo", table)])
    spec = spec_of(path, tmp_path)

    (structure,) = spec.structures
    assert [(f.range, f.name, f.acronym) for f in structure.fields] == [
        ("03", "Foo Slave Enable", "FSE"),
        ("02", "Foo Master Enable", "FME"),
    ]
    assert [(e.code, e.message, e.found, e.source.figure_nr) for e in spec.errata] == [
        (
            "acronym",
            "Field 02 Foo Master Enable: the parenthesis of its acronym 'FME' "
            "is not closed",
            "FME",
            1,
        )
    ]
    assert [d.code for d in spec.diagnostics] == []


def values_of_table(header, *rows):
    """The table of values senfd makes of a figure of 'header' and 'rows'"""

    from senfd.documents.normalized import normalize_figure
    from senfd.documents.plain import Figure
    from senfd.documents.spec import add_figure
    from senfd.tables import Cell, Row, Table

    texts = [("Figure 1: Foo Kinds",), header, *rows]
    table = Table(rows=[Row(cells=[Cell(text=t) for t in row]) for row in texts])
    figure = Figure(
        figure_nr=1, caption="Figure 1: Foo Kinds", description="Foo Kinds", table=table
    )
    document = SpecDocument()
    add_figure(document, normalize_figure(figure, []), "example")
    (values,) = document.values
    return values


def test_the_value_of_an_entry_is_its_code_whatever_the_header_of_the_column():
    """A table listing things in its first column and their codes in a column
    of a header senfd has no name for: the code is the value, and what the
    first column lists is the name"""

    values = values_of_table(
        ("Foo", "Kind Designator", "Definition"),
        ("Header", "N/A", "What the foos begin with."),
        ("Ding Foo", "1h", "A foo that dings."),
        ("Ring Foo", "2h", "A foo that rings."),
    )
    assert [(e.value, e.value_column, e.name) for e in values.entries] == [
        ("N/A", "kind_designator", "Header"),
        ("1h", "kind_designator", "Ding Foo"),
        ("2h", "kind_designator", "Ring Foo"),
    ]
    assert values.entries[1].columns == {}
    assert values.entries[1].description == "A foo that dings."


def test_the_code_of_an_entry_is_the_one_no_other_entry_has():
    """Of the columns of codes, as the parts an opcode is combined from, the
    value is in the one whose codes differ entry by entry; the column of
    names is the name"""

    values = values_of_table(
        ("Foo Name", "Function", "Direction", "Combined Opcode 2", "Foo Description"),
        ("DingReq", "0000000b", "0b", "00h", "Ding Request: asks for a ding"),
        ("DingResp", "0000000b", "1b", "01h", "Ding Response: answers it"),
        ("RingReq", "0000001b", "0b", "02h", "Ring Request: asks for a ring"),
    )
    assert [(e.value, e.value_column, e.name) for e in values.entries] == [
        ("00h", "opcode", "DingReq"),
        ("01h", "opcode", "DingResp"),
        ("02h", "opcode", "RingReq"),
    ]
    assert values.entries[0].columns == {
        "function": "0000000b",
        "direction": "0b",
        "foo_description": "Ding Request: asks for a ding",
    }


def test_an_offset_an_expression_goes_on_from_is_a_code():
    """A table of registers by where they start, the later ones at an offset
    counted from the first: the start is the value, the symbol a column"""

    values = values_of_table(
        ("Start", "End", "Symbol", "Name"),
        ("1000h", "1003h", "F0DBL", "Foo 0 Doorbell"),
        (
            "1000h + (1 * (4 << F.STRD))",
            "1003h + (1 * (4 << F.STRD))",
            "F1DBL",
            "Foo 1",
        ),
    )
    assert [(e.value, e.value_column, e.name) for e in values.entries] == [
        ("1000h", "start", "Foo 0 Doorbell"),
        ("1000h + (1 * (4 << F.STRD))", "start", "Foo 1"),
    ]
    assert values.entries[0].columns == {"end": "1003h", "symbol": "F0DBL"}


def test_a_command_is_the_name_of_the_opcode_a_table_gives_it():
    values = values_of_table(
        ("Command", "Opcode", "Foo Support Requirements"),
        ("Ding", "01h", "M"),
        ("Ring", "02h", "O"),
    )
    assert [(e.value, e.name) for e in values.entries] == [
        ("01h", "Ding"),
        ("02h", "Ring"),
    ]


def test_columns_of_codes_that_repeat_are_no_value():
    """The parts of a version are codes of more than one entry, the major
    part here, so that the minor part differing entry by entry is no code of
    the entry either; the entry is by its first column, as in a table of no
    codes"""

    values = values_of_table(
        ("Foo Versions", "MJR Field", "MNR Field"),
        ("Foo 1.0", "1h", "0h"),
        ("Foo 1.1", "1h", "1h"),
        ("Foo 1.2", "1h", "2h"),
    )
    assert [(e.value, e.value_column, e.name) for e in values.entries] == [
        ("Foo 1.0", "foo_versions", None),
        ("Foo 1.1", "foo_versions", None),
        ("Foo 1.2", "foo_versions", None),
    ]


def test_the_column_combining_the_codes_of_others_is_the_value():
    values = values_of_table(
        ("07:02", "01:00", "Combined Foo Type", "Command"),
        ("0000 00b", "00b", "00h", "Ding"),
        ("0000 00b", "01b", "01h", "Ring"),
        ("0000 01b", "00b", "04h", "Sing"),
    )
    assert [(e.value, e.value_column, e.name) for e in values.entries] == [
        ("00h", "combined_foo_type", "Ding"),
        ("01h", "combined_foo_type", "Ring"),
        ("04h", "combined_foo_type", "Sing"),
    ]


def test_an_entry_named_by_its_description_keeps_the_code_as_its_value():
    """Where some descriptions begin with a name and others do not, the value
    of every entry is the code, not the name of those that have one"""

    values = values_of_table(
        ("Foo Identifier List", "Description"),
        ("00h", "Default Foo: The foo as made."),
        ("01h", "A foo of no name."),
        ("02h to FFh", "Reserved"),
    )
    assert [(e.value, e.value_column, e.name) for e in values.entries] == [
        ("00h", "foo_identifier_list", "Default Foo"),
        ("01h", "foo_identifier_list", None),
        ("02h to FFh", "foo_identifier_list", "Reserved"),
    ]


def test_an_entry_of_a_column_headed_as_values_is_named_by_the_first_column():
    """A table listing things in its first column and their codes in a column
    whose header says it holds values, as "Directive" and "Directive Type
    Value": what the first column lists is the name of each entry"""

    values = values_of_table(
        ("Foo", "Foo Type Value", "Reference"),
        ("Ding", "00h", "1.2"),
        ("Ring", "01h", "1.3"),
        ("Sing", "0Fh", ""),
    )
    assert [(e.value, e.value_column, e.name) for e in values.entries] == [
        ("00h", "foo_type_value", "Ding"),
        ("01h", "foo_type_value", "Ring"),
        ("0Fh", "foo_type_value", "Sing"),
    ]
    assert values.entries[0].columns == {"reference": "1.2"}


def figure_of(number, caption, header, *rows):
    """A figure of a table of 'header' and 'rows', as the documents have it"""

    from senfd.documents.plain import Figure
    from senfd.tables import Cell, Row, Table

    texts = [(f"Figure {number}: {caption}",), header, *rows]
    cells = [[t if isinstance(t, Cell) else Cell(text=t) for t in row] for row in texts]
    return Figure(
        figure_nr=number,
        caption=f"Figure {number}: {caption}",
        description=caption,
        table=Table(rows=[Row(cells=row) for row in cells]),
    )


def document_of(*figures, stem="example"):
    """The specification document senfd makes of 'figures'"""

    from senfd.documents.normalized import normalize_figure
    from senfd.documents.spec import add_figure, resolve

    document = SpecDocument()
    document.meta.stem = stem
    for figure in figures:
        add_figure(document, normalize_figure(figure, []), stem)
    return resolve(document)


FOO_TYPES = (
    ("Foo Types", ("Value", "Definition"))
    + (("0h", "Ding: A foo that dings."),)
    + (("1h", "Ring: A foo that rings."), ("2h to Fh", "Reserved"))
)
BAR_KINDS = ("Bar Kinds", ("Value", "Definition")) + (
    ("0h", "Sing: A bar that sings."),
    ("1h to Fh", "Reserved"),
)


def test_a_field_is_linked_to_the_table_of_its_values_that_its_description_names():
    """As CNS of Identify gives no values and says "Refer to Figure 336", and
    CSI names that figure and the figure of the Command Set Identifiers: the
    table linked is the one named for the field"""

    spec = document_of(
        figure_of(
            1,
            "Foo Data Structure",
            ("Bits", "Description"),
            ("15:12", "Foo Type (FTYPE): The type of the foo. Refer to Figure 2 ."),
            (
                "11:08",
                "Bar Kind (BK): This field is foo type specific (refer to "
                "Figure 2). The kinds are listed in Figure 3.",
            ),
            ("07:05", "Foo Level (FL): The level, for the types of Figure 2."),
            ("04", "Bar Kind Enable (BKE): Enables the kinds of Figure 3."),
            ("03:00", "Foo Count (FC): The number of foos, of no Figure 9."),
        ),
        figure_of(2, *FOO_TYPES),
        figure_of(3, *BAR_KINDS),
    )
    (structure,) = spec.structures
    links = {
        f.acronym: f.values_in.figure_nr if f.values_in else None
        for f in structure.fields
    }

    # Foo Level is of another name, and Bar Kind Enable of one bit only
    assert links == {"FTYPE": 2, "BK": 3, "FL": None, "BKE": None, "FC": None}
    assert structure.fields[0].values_in == spec.values[0].source


def test_a_field_giving_its_values_is_linked_to_no_table():
    from senfd.tables import Cell, Row, Table

    values = Table(
        rows=[
            Row(cells=[Cell(text=t) for t in row])
            for row in (("Value", "Definition"), ("0h", "Ding"), ("1h", "Ring"))
        ]
    )
    described = Cell(text="Foo Type (FTYPE): Refer to Figure 2.", tables=[values])
    spec = document_of(
        figure_of(
            1, "Foo Data Structure", ("Bits", "Description"), ("03:00", described)
        ),
        figure_of(2, *FOO_TYPES),
    )
    (field,) = spec.structures[0].fields

    assert [v.value for v in field.values] == ["0h", "1h"]
    assert field.values_in is None


def test_the_link_to_a_table_of_values_is_of_the_same_document_when_merged():
    """Two documents each have a Figure 2; a field is linked to the one of
    its own document, and the link is made again when the documents merge"""

    layout = figure_of(
        1,
        "Foo Data Structure",
        ("Bits", "Description"),
        ("03:00", "Foo Type (FTYPE): Refer to Figure 2."),
    )
    first = document_of(layout, figure_of(2, *FOO_TYPES), stem="first")
    second = document_of(figure_of(2, *FOO_TYPES), stem="second")
    merged = merge([second, first])
    again = SpecDocument.model_validate_json(merged.to_json())

    for spec in (merged, again):
        (field,) = spec.structures[0].fields
        assert (field.values_in.document, field.values_in.figure_nr) == ("first", 2)
