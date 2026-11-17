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


def test_the_i_o_commands_of_every_i_o_command_set_are_named_common_i_o():
    """Base 2.4 Figure 645, "Opcodes for I/O Commands", lists the I/O
    commands of every I/O command set, as Flush; it is no command set "I/O" """

    from senfd.documents.spec import command_set_name

    assert command_set_name("I/O") == "Common I/O"
    assert command_set_name("NVM Command Set I/O") == "NVM"
    assert command_set_name("Admin") == "Admin"


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


def test_an_entry_takes_its_name_from_the_first_column():
    """A table with names in its first column and codes in a column whose
    header marks it as values, for example "Directive" and "Directive Type
    Value". Each entry is named by its first column."""

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


def test_a_field_is_linked_to_the_table_of_values_named_for_it():
    """CNS of Identify lists no values and says "Refer to Figure 336". CSI
    refers to that figure and to the figure of the Command Set Identifiers.
    Each field is linked to the table named for it."""

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


def test_a_field_that_lists_its_values_is_not_linked_to_a_table():
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


def test_a_field_is_linked_to_the_table_of_its_own_document():
    """Two documents each have a Figure 2. A field is linked to the Figure 2
    of its own document, and the link is made again when the documents are
    merged."""

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


FOO_FORMAT = (
    "Foo Format Data Structure",
    ("Bits", "Description"),
    ("31:16", "Reserved"),
    ("15:00", "Foo Size (FS)"),
)


def test_numbered_fields_with_rows_left_out_are_an_array():
    """Identify Namespace lists LBAF0, LBAF1, "..." and LBAF63, each
    "defined in Figure 125". Identify I/O Command Set lists IOCSC0 to
    IOCSC511, each "an I/O Command Set Vector", a structure whose caption
    does not call it a data structure."""

    from senfd.documents.spec import Array

    spec = document_of(
        figure_of(
            1,
            "Foo List Data Structure",
            ("Bytes", "Description"),
            ("03:00", "Number of Foo Formats (NFF)"),
            (
                "07:04",
                "Foo Format 0 Support (FF0): The Foo Format is defined in "
                "Figure 2. More of it is in Figure 3.",
            ),
            ("11:08", "Foo Format 1 Support (FF1): Defined in Figure 2."),
            ("...", ""),
            ("35:32", "Foo Format 7 Support (FF7): Defined in Figure 2."),
            ("43:36", "Bar Set 0 (BS0): This field contains a Bar Vector."),
            ("51:44", "Bar Set 1 (BS1): This field contains a Bar Vector."),
            ("...", ""),
            ("67:60", "Bar Set 3 (BS3)"),
            ("75:68", "Bar Vector Count (BVC): How many a Bar Vector holds."),
        ),
        figure_of(2, *FOO_FORMAT),
        figure_of(
            3,
            "Foo Format Extension Data Structure",
            ("Bits", "Description"),
            ("63:00", "Foo Extension (FE)"),
        ),
        figure_of(
            4,
            "Bar Vector",
            ("Bits", "Description"),
            ("63:01", "Reserved"),
            ("00", "Bar Enabled (BE)"),
        ),
    )
    fields = {f.acronym: f for f in spec.structures[0].fields}
    formats = dict(
        name="Foo Format Support", acronym="FF", first=0, count=8, stride=4, lower=4
    )

    assert fields["FF0"].array == Array(index=0, **formats)
    assert fields["FF7"].array == Array(index=7, **formats)
    assert fields["BS3"].array == Array(
        name="Bar Set", acronym="BS", index=3, first=0, count=4, stride=8, lower=36
    )
    assert fields["NFF"].array is None and fields["BVC"].array is None
    # Of the figures FF0 names, the structure of 4 bytes lays it out; the
    # entries of BS have the structure that their descriptions name, BS3 too
    linked = {
        a: f.structure.figure_nr if f.structure else None for a, f in fields.items()
    }
    assert linked == {
        "NFF": None,
        "FF0": 2,
        "FF1": 2,
        "FF7": 2,
        "BS0": 4,
        "BS1": 4,
        "BS3": 4,
        "BVC": None,
    }
    assert [(s.name, s.kind) for s in spec.structures][2:] == [
        ("Foo Format Extension", "data_structure"),
        ("Bar Vector", "data_structure"),
    ]


def test_an_array_whose_last_entry_is_given_by_a_formula_has_no_count():
    spec = document_of(
        figure_of(
            1,
            "Foo List Data Structure",
            ("Bytes", "Description"),
            ("07:00", "Number of Entries (NUMENT)"),
            ("15:08", "Entry 0"),
            ("23:16", "Entry 1"),
            ("...", ""),
            ("(NUMENT*8)+7:(NUMENT*8)", "Entry NUMENT-1"),
        )
    )
    arrays = [f.array for f in spec.structures[0].fields]

    assert arrays[0] is None
    assert [
        (a.name, a.index, a.first, a.count, a.stride, a.lower) for a in arrays[1:]
    ] == [
        ("Entry", 0, 0, None, 8, 8),
        ("Entry", 1, 0, None, 8, 8),
        ("Entry", None, 0, None, 8, 8),
    ]


def test_numbered_fields_at_the_wrong_offsets_are_not_an_array():
    """With entries of 4 bytes from byte 0, entry 7 is at byte 28, not 36.
    Fields with different names and rows left out between them are not an
    array either."""

    spec = document_of(
        figure_of(
            1,
            "Foo List Data Structure",
            ("Bytes", "Description"),
            ("03:00", "Foo 0 (F0)"),
            ("07:04", "Foo 1 (F1)"),
            ("...", ""),
            ("39:36", "Foo 7 (F7)"),
            ("43:40", "Bar Low (BL1)"),
            ("...", ""),
            ("51:48", "Baz High (BH2)"),
        )
    )

    assert [f.array for f in spec.structures[0].fields] == [None] * 5


def test_a_field_with_its_own_subfields_is_not_linked_to_a_structure():
    """LBAF0 of the Exported Controller Configuration State lays out the
    fields of an LBA Format in its own description."""

    from senfd.tables import Cell, Row, Table

    nested = Table(
        rows=[
            Row(cells=[Cell(text=t) for t in row])
            for row in (FOO_FORMAT[1], *FOO_FORMAT[2:])
        ]
    )
    described = Cell(text="Foo Format 0 (FF0): As in Figure 2.", tables=[nested])
    spec = document_of(
        figure_of(
            1,
            "Foo State",
            ("Bytes", "Description"),
            ("03:00", described),
            ("07:04", "Foo Format Kept (FFK): A format, as in Figure 2."),
        ),
        figure_of(2, *FOO_FORMAT),
    )
    laid_out, kept = spec.structures[0].fields

    assert [f.acronym for f in laid_out.fields] == [None, "FS"]
    assert laid_out.structure is None
    assert kept.structure == spec.structures[1].source
    assert spec.structures[0].kind == "other"


def test_an_unnamed_row_with_a_nested_table_is_named_after_its_range():
    """A byte that the figure gives no name, with a table of its bits in its
    cell. The row is not a heading of the rows below it, and the field is
    named after its range, so the fields of its bits are in the data
    model."""

    from senfd.tables import Cell, Row, Table

    bits = Table(
        rows=[
            Row(cells=[Cell(text=t) for t in row])
            for row in (
                ("Bits", "Description"),
                ("07:01", "Reserved"),
                ("00", "Foo Active (FA): Whether the foo is active."),
            )
        ]
    )
    spec = document_of(
        figure_of(
            1,
            "Foo Descriptor Data Structure",
            ("Bytes", "Description"),
            ("00", Cell(text="", tables=[bits])),
            ("02:01", Cell(text="", tables=[bits])),
            ("03", "Foo Type (FT)"),
        )
    )
    fields = spec.structures[0].fields

    assert [(f.range, f.name, f.section) for f in fields] == [
        ("00", "Byte 00", None),
        ("02:01", "Bytes 02:01", None),
        ("03", "Foo Type", None),
    ]
    assert [(f.range, f.acronym) for f in fields[0].fields] == [
        ("07:01", None),
        ("00", "FA"),
    ]
    assert [d.code for d in spec.diagnostics] == []


def table_of(*rows):
    """A table of 'rows', a cell given as text or as a cell"""

    from senfd.tables import Cell, Row, Table

    return Table(
        rows=[
            Row(cells=[c if isinstance(c, Cell) else Cell(text=c) for c in row])
            for row in rows
        ]
    )


def holding(text, *tables, merged=None):
    """A cell of 'text' holding 'tables'"""

    from senfd.tables import Cell

    return Cell(text=text, tables=list(tables), merged=merged)


def foo_receive():
    """Command Dword 13 of Foo Receive, as that of Zone Management Receive
    and Zone Management Send: fields whose cells hold a table by the value
    of Foo Action, the field of bits 07:00"""

    options = table_of(
        ("Value", "Definition"),
        ("0h", "List all foos."),
        ("1h", "List the idle foos."),
        ("2h to FFh", "Reserved"),
    )
    lifetime = table_of(("Value", "Definition"), ("0h", "No estimate"), ("1h", "Short"))
    managed = table_of(
        ("Bits", "Description"),
        ("07:06", "Reserved"),
        ("05:00", holding("Foo Lifetime (FL): An estimate.", lifetime)),
    )
    partial = "Partial Ding (PD): If this bit is set to '1', the ding is partial."
    return figure_of(
        1,
        "Foo Receive \u2013 Command Dword 13",
        ("Bits", "Description"),
        ("31:25", "Reserved"),
        (
            "24:17",
            holding(
                "Foo Management (FM): Attributes of the action.",
                table_of(
                    ("Foo Action", "Definition"),
                    ("Ding", holding("", managed)),
                    ("All other values", "Reserved"),
                ),
            ),
        ),
        (
            "16",
            holding(
                "Foo Action Specific Features (FASF):",
                table_of(
                    ("Foo Action", "Definition"),
                    ("Ding", partial),
                    ("Loud Ding", holding(partial, merged="up")),
                    ("All others", "Reserved"),
                ),
            ),
        ),
        (
            "15:08",
            holding(
                "Foo Action Specific (FAS):",
                table_of(
                    ("Foo\nAction", "Description"),
                    ("Ding", holding("Ding Options:", options)),
                    ("Loud\nDing", holding("Ding Options:", merged="up")),
                    ("Ring", "A sentence that names nothing."),
                    ("All other values", "Reserved"),
                ),
            ),
        ),
        (
            "07:00",
            holding(
                "Foo Action (FA):",
                table_of(
                    ("Value", "Definition"),
                    ("00h", "Ding: Dings."),
                    ("01h", "Loud Ding: Dings loudly."),
                    ("02h", "Ring: Rings."),
                    ("03h to FFh", "Reserved"),
                ),
            ),
        ),
    )


def test_a_table_headed_by_another_field_gives_the_cases():
    """ZRAS of Zone Management Receive is the Reporting Options, with their
    values, when ZRA is Report Zones or Extended Report Zones, and reserved
    for all other values. The rows are not values of ZRAS."""

    spec = document_of(foo_receive())
    fields = {f.acronym: f for f in spec.dwords["foo_receive"][0].fields}
    specific = fields["FAS"]
    ding, ring, others = specific.cases

    assert specific.values == []
    assert (ding.selector, ding.otherwise, ding.name, ding.role) == (
        "FA",
        False,
        "Ding Options",
        "field",
    )
    assert [(w.name, w.value) for w in ding.when] == [("Ding", 0), ("Loud Ding", 1)]
    assert [(v.value, v.name, v.description) for v in ding.values] == [
        ("0h", None, "List all foos."),
        ("1h", None, "List the idle foos."),
        ("2h to FFh", "Reserved", ""),
    ]
    assert ding.values[0].typed["value"].lower == 0
    assert (ring.name, ring.description, [w.value for w in ring.when]) == (
        None,
        "A sentence that names nothing.",
        [2],
    )
    assert (others.otherwise, others.when, others.name, others.role) == (
        True,
        [],
        "Reserved",
        "reserved",
    )
    # The values of the field deciding the cases are its own
    assert [v.value for v in fields["FA"].values][:2] == ["00h", "01h"]
    assert fields["FA"].cases == []


def test_a_case_has_the_name_and_the_layout_of_the_field():
    """ZSASO of Zone Management Send is ZRWA Allocation (ZRWAA) when ZSA is
    Open Zone, and ZM has the Data Lifetime in its bits 05:00."""

    spec = document_of(foo_receive())
    fields = {f.acronym: f for f in spec.dwords["foo_receive"][0].fields}
    partial, others = fields["FASF"].cases
    managed, _ = fields["FM"].cases

    assert (partial.name, partial.acronym, partial.description) == (
        "Partial Ding",
        "PD",
        "If this bit is set to '1', the ding is partial.",
    )
    assert [(w.name, w.value) for w in partial.when] == [("Ding", 0), ("Loud Ding", 1)]
    assert (others.otherwise, others.role) == (True, "reserved")
    assert fields["FASF"].values == [] and fields["FM"].values == []
    assert (managed.name, [w.value for w in managed.when]) == (None, [0])
    assert [(f.range, f.name, f.acronym, f.role) for f in managed.fields] == [
        ("07:06", "Reserved", None, "reserved"),
        ("05:00", "Foo Lifetime", "FL", "field"),
    ]
    assert [v.value for v in managed.fields[1].values] == ["0h", "1h"]


def test_a_table_not_headed_by_another_field_gives_values():
    """A table of two columns whose first header names no field of the
    layout remains the values of its field, whatever its rows hold."""

    spec = document_of(
        figure_of(
            1,
            "Foo Receive \u2013 Command Dword 13",
            ("Bits", "Description"),
            (
                "31:08",
                holding(
                    "Foo Kind (FK):",
                    table_of(("Bar Action", "Definition"), ("Ding", "Dings.")),
                ),
            ),
            ("07:00", "Foo Action (FA)"),
        )
    )
    kind = spec.dwords["foo_receive"][0].fields[0]

    assert kind.cases == []
    assert [(v.value, v.description) for v in kind.values] == [("Ding", "Dings.")]


def test_a_case_for_a_code_has_that_code_as_its_value():
    """The Further Error Information of the Terminate Connection Request
    PDUs depends on the Fatal Error Status, and the rows give the status as
    "01h". A range of codes is not a single value."""

    spec = document_of(
        figure_of(
            1,
            "Foo Request Data Structure",
            ("Bytes", "Description"),
            ("01:00", "Foo Error Status (FES)"),
            (
                "05:02",
                holding(
                    "Foo Error Information (FEI):",
                    table_of(
                        ("FES", "Definition"),
                        ("00", "Reserved"),
                        ("01h", "Foo Offset: Where the error is."),
                        ("02h to FFFFh", "Reserved"),
                    ),
                ),
            ),
        )
    )
    cases = spec.structures[0].fields[1].cases

    assert [(c.selector, c.name, c.role) for c in cases] == [
        ("FES", "Reserved", "reserved"),
        ("FES", "Foo Offset", "field"),
        ("FES", "Reserved", "reserved"),
    ]
    assert [[(w.name, w.value) for w in c.when] for c in cases] == [
        [("00", 0)],
        [("01h", 1)],
        [("02h to FFFFh", None)],
    ]


SECTIONS = {
    "5.1": "Identify Controller Data Structure (CNS 01h)",
    "5.2": "Active Namespace ID list (CNS 02h)",
    "5.3": "Get Underlying Controller List (CNS 21h)",
    "5.4": "I/O Command Set specific Identify Controller (CNS 06h, CSI 04h)",
    "5.5": "Personality (Personality Identifier 3h)",
    "5.6": "Event of another table (Event Type 00h)",
}


def cns_values(rows):
    """A table of CNS values of 'rows', each a value, its reference and
    whether its row says Reserved, as the Identify command's"""

    from senfd.documents.spec import Entry, Source, Values

    return Values(
        kind="cns_values",
        name="Identify",
        columns=["cns_value", "description", "reference"],
        entries=[
            Entry(
                value=value,
                value_column="cns_value",
                columns={"reference": reference}
                | ({"event": "Reserved"} if reserved else {}),
            )
            for value, reference, reserved in rows
        ],
        source=Source(document="Base", figure_nr=336),
    )


def test_a_code_is_named_by_the_section_its_reference_cites():
    from senfd.documents.spec import name_by_sections

    document = SpecDocument()
    document.values.append(
        cns_values(
            [
                ("01h", "5.1", False),
                ("06h", "5.4", False),
                ("03h", "5.5", False),
                ("1Fh", "", False),
                ("00h", "5.6", True),
                ("0Bh to 0Fh", "5.1", False),
            ]
        )
    )
    name_by_sections(document, SECTIONS)
    assert [e.name for e in document.values[0].entries] == [
        "Identify Controller Data Structure",
        "I/O Command Set specific Identify Controller",
        "Personality",
        None,
        None,
        None,
    ]
    assert document.errata == []


def test_a_reference_to_the_section_of_another_code_is_a_candidate_erratum():
    """CNS 14h of Base 2.4 cites the section of CNS 21h, and CNS 02h cites "0";
    each takes the section whose title names it, where there is one"""

    from senfd.documents.spec import name_by_sections

    document = SpecDocument()
    document.values.append(
        cns_values([("14h", "5.3", False), ("02h", "0", False), ("01h", "5.1", False)])
    )
    name_by_sections(document, SECTIONS)
    assert [e.name for e in document.values[0].entries] == [
        None,
        "Active Namespace ID list",
        "Identify Controller Data Structure",
    ]
    (erratum,) = document.errata
    assert (erratum.code, erratum.found) == ("reference", "5.3")
    assert erratum.message.startswith(
        "14h: the reference 5.3 is the section of CNS 21h"
    )


def test_a_field_records_its_range_under_each_condition_heading_the_ranges():
    """As the PDU Header Digest of NVMe over TCP 1.3 Figure 30, which is bytes
    75:72 when HDGSTF=1 and not present when HDGSTF=0"""

    from senfd.tables import Cell

    spec = document_of(
        figure_of(
            1,
            "Foo PDU",
            ("Bytes", Cell(text="Bytes", merged="left"), "Description"),
            ("03:00", "03:00", "Foo Header (FH): The header."),
            ("HDGSTF=1", "HDGSTF=0", ""),
            ("07:04", "Not present", "PDU Header Digest (HDGST): The digest."),
        )
    )
    (structure,) = spec.structures
    digest = structure.fields[-1]
    assert (digest.acronym, digest.range, digest.upper, digest.lower) == (
        "HDGST",
        "07:04",
        7,
        4,
    )
    assert [p.model_dump() for p in digest.placements] == [
        {"condition": "HDGSTF=1", "range": "07:04", "upper": 7, "lower": 4},
        {"condition": "HDGSTF=0", "range": None, "upper": None, "lower": None},
    ]
    assert structure.fields[0].placements == []


def test_a_feature_has_the_dwords_of_the_section_its_identifier_names():
    """Base 2.4 describes CDW12 of Flexible Data Placement Events (1Eh) in a
    figure whose caption names Flexible Data Placement (1Dh), and Reservation
    Notification Mask (82h) in one whose caption names no feature; the
    section title gives the identifier of each"""

    from senfd.documents.spec import Dwords, Feature, Source, link_features

    def source(figure_nr, section_title):
        return Source(
            document="example",
            figure_nr=figure_nr,
            section="1.1",
            section_title=section_title,
        )

    document = SpecDocument()
    for identifier, name in ((0x1D, "Foo Placement"), (0x1E, "Foo Placement Events")):
        document.features[name] = Feature(
            identifier=identifier, name=name, source=source(1, "Feature Identifiers")
        )
    document.dwords = {
        "foo_placement": [
            Dwords(lower=11, upper=11, source=source(2, "Foo Placement")),
            Dwords(
                lower=12,
                upper=12,
                source=source(4, "Foo Placement Events (Feature Identifier 1Eh)"),
            ),
        ],
        "foo_mask": [
            Dwords(
                lower=11,
                upper=11,
                source=source(3, "Foo Placement Events (Feature Identifier 1Eh)"),
            )
        ],
    }
    # Of a key, a figure the section places and one nothing places
    document.dwords["bar"] = [
        Dwords(
            lower=13,
            upper=13,
            source=source(5, "Foo Placement Events (Feature Identifier 1Eh)"),
        ),
        Dwords(lower=14, upper=14, source=source(6, "Bar")),
    ]
    used: set = set()
    link_features(document, used)

    features = document.features
    assert [d.source.figure_nr for d in features["Foo Placement"].sqe] == [2]
    assert [d.source.figure_nr for d in features["Foo Placement Events"].sqe] == [
        3,
        4,
        5,
    ]
    assert {"foo_placement", "foo_mask"} <= used

    from senfd.documents.spec import unassigned_of

    unassigned = unassigned_of(document.dwords, used)
    assert {k: [d.source.figure_nr for d in v] for k, v in unassigned.items()} == {
        "bar": [6]
    }


def test_a_reference_to_the_section_of_another_kind_of_code_names_the_value():
    """Only a section titled by the table's own label, as "(CNS 21h)" for
    the CNS values, names another value; a section titled by another label,
    as "(Personality Identifier 3h)", is the section the value cites. A code
    that two titles name, as CNS 07h of two command sets, takes neither."""

    from senfd.documents.spec import name_by_sections

    sections = SECTIONS | {
        "5.7": "Foo of the NVM Command Set (CNS 07h, CSI 00h)",
        "5.8": "Foo of the ZNS Command Set (CNS 07h, CSI 02h)",
    }
    document = SpecDocument()
    document.values.append(
        cns_values([("01h", "5.1", False), ("05h", "5.5", False), ("07h", "0", False)])
    )
    name_by_sections(document, sections)
    assert [e.name for e in document.values[0].entries] == [
        "Identify Controller Data Structure",
        "Personality",
        None,
    ]
    assert document.errata == []


def test_a_byte_diagram_marking_the_msb_in_the_highest_byte_is_little_endian():
    from senfd.documents.spec import byte_order_of

    assert byte_order_of({"msb_byte": "3", "lsb_byte": "0"}) == "little-endian"
    assert byte_order_of({"msb_byte": "0", "lsb_byte": "3"}) == "big-endian"
    assert byte_order_of({"msb_byte": "2", "lsb_byte": "2"}) is None
    assert byte_order_of({}) is None


def test_completion_dwords_go_to_the_feature_their_section_names():
    from senfd.documents.spec import Dwords, Feature, Source, link_features

    def source(figure_nr, section_title):
        return Source(
            document="example",
            figure_nr=figure_nr,
            section="1.1",
            section_title=section_title,
        )

    document = SpecDocument()
    document.features["Foo"] = Feature(
        identifier=0x82, name="Foo", source=source(1, "Feature Identifiers")
    )
    document.dwords = {
        "cqe:bar_configuration": [
            Dwords(lower=0, upper=0, source=source(2, "Foo (Feature Identifier 82h)"))
        ]
    }
    used: set = set()
    link_features(document, used)
    assert [d.source.figure_nr for d in document.features["Foo"].cqe] == [2]
    assert document.features["Foo"].sqe == []
    assert "cqe:bar_configuration" in used


def test_a_figure_of_a_feature_section_goes_to_the_feature_not_the_command():
    """Base 2.4 gives Command Dword 11 of Host Metadata, Features 7Dh, 7Eh
    and 7Fh, in a figure captioned "Set Features - Command Dword 11"; the
    figure is the features', and Set Features keeps its own figures"""

    from senfd.documents.spec import (
        Command,
        CommandSet,
        Dwords,
        Entry,
        Source,
        Values,
        alias,
        resolve,
    )

    def source(figure_nr, section_title):
        return Source(
            document="example",
            figure_nr=figure_nr,
            section="1.1",
            section_title=section_title,
        )

    document = SpecDocument()
    document.command_sets = {
        "admin": CommandSet(
            name="Admin",
            commands={
                "set_features": Command(
                    name="Set Features", opcode=9, source=source(1, "Opcodes")
                )
            },
        )
    }
    metadata = "Host Metadata (Feature Identifier 7Dh), (Feature Identifier 7Eh), "
    document.dwords = {
        "set_features": [
            Dwords(lower=10, upper=10, source=source(2, "Set Features command")),
            Dwords(
                lower=11,
                upper=11,
                source=source(3, metadata + "(Feature Identifier 7Fh)"),
            ),
        ]
    }
    names = {"7Dh": "Foo Metadata", "7Eh": "Bar Metadata", "7Fh": "Baz Metadata"}
    document.values = [
        Values(
            kind="feature_identifiers",
            name="Feature Identifiers",
            columns=["identifier", "feature_name"],
            source=source(4, "Feature Identifiers"),
            entries=[Entry(value=v, name=n) for v, n in names.items()],
        )
    ]
    resolve(document)

    command = document.command_sets["admin"].commands["set_features"]
    assert [d.source.figure_nr for d in command.sqe] == [2]
    for name in names.values():
        feature = document.features[alias(name)]
        assert [d.source.figure_nr for d in feature.sqe] == [3]
    assert document.unassigned == {}


def test_a_footnote_marker_after_the_last_sentence_is_a_footnote():
    """Base 2.4 marks footnote 7 on CNS descriptions, as "... processing the
    command.7", and footnote 1 on fields of Format NVM, as "... specific
    definition.1"; the marker is no part of the text"""

    from senfd.documents.spec import entry_of, footnoted

    assert footnoted("Its definition.1") == ("Its definition.", [1])
    assert footnoted("Of the field.2, 3") == ("Of the field.", [2, 3])
    assert footnoted("Revision 2.1") == ("Revision 2.1", [])
    assert footnoted("Set to 1.") == ("Set to 1.", [])
    entry = entry_of({"value": "05h", "description": "Foo for the command.7"})
    assert (entry.description, entry.footnotes) == ("Foo for the command.", [7])


def test_a_field_has_the_footnotes_marked_at_the_end_of_its_description():
    spec = document_of(
        figure_of(
            1,
            "Foo Structure",
            ("Bytes", "Description"),
            ("03:00", "Foo Header (FH): The header, of a specific definition.1"),
        )
    )
    (structure,) = spec.structures
    (field,) = structure.fields
    assert (field.description, field.footnotes) == (
        "The header, of a specific definition.",
        [1],
    )


def test_a_marker_read_as_superscript_is_a_footnote_of_the_name_value_or_column():
    """The readers give a footnote marker as superscript digits, as "List
    Exported Controllers1" of Base 2.4 Figure 375, "000b1" of Figure 542 and
    "Number of Placement Handles 2" of NVM 1.3 Figure 134; the marker is no
    part of the text, and digits of the text and an exponent are kept"""

    from senfd.documents.spec import entry_of, typed_of

    entry = entry_of(
        {
            "value": "03h",
            "management_operation": "List Exported Controllers\u00b9",
            "scope": "NVM subsystem\u00b9 / Namespace\u00b2",
        }
    )
    assert entry.columns == {
        "management_operation": "List Exported Controllers",
        "scope": "NVM subsystem / Namespace",
    }
    assert entry.footnotes == [1, 2]
    entry = entry_of({"value": "000b\u00b9", "description": "Not supported\u00b2"})
    assert (entry.value, entry.description, entry.footnotes) == (
        "000b",
        "Not supported",
        [1, 2],
    )
    entry = entry_of({"value": "1h", "name": "TSEN1", "description": "2\u00b9\u2076"})
    assert (entry.name, entry.description, entry.footnotes) == (
        "TSEN1",
        "2\u00b9\u2076",
        [],
    )
    typed = typed_of("000b\u00b9")
    assert typed is not None and (typed.lower, typed.footnotes) == (0, [1])

    spec = document_of(
        figure_of(
            1,
            "Foo Structure",
            ("Bytes", "Description"),
            ("01:00", "Number of Foos \u00b2 (NFOO): The number."),
            ("03:02", "Foo 0 Associated RUH\u00b2: The handle."),
        )
    )
    (structure,) = spec.structures
    assert [(f.name, f.acronym, f.footnotes) for f in structure.fields] == [
        ("Number of Foos", "NFOO", [2]),
        ("Foo 0 Associated RUH", None, [2]),
    ]


def test_an_entry_naming_a_value_of_another_field_links_to_it():
    """Reporting Options 1h of Zone Management Receive, "List the zones in the
    ZSE:Empty state.", names value 1h of the field ZS of the Zone Descriptor,
    ZNS 1.5 Figure 38; a field that has only some of the names named, and an
    entry with a name of its own, are not linked"""

    from senfd.documents.spec import (
        Bits,
        Entry,
        Source,
        Structure,
        Values,
        link_named_values,
    )

    def field(acronym, names):
        return Bits(
            name=acronym,
            acronym=acronym,
            unit="bits",
            role="field",
            kind="span",
            range="7:4",
            upper=7,
            lower=4,
            width=4,
            values=[Entry(value=v, name=n) for v, n in names],
        )

    document = SpecDocument()
    document.structures = [
        Structure(
            name="Zone Descriptor",
            kind="data_structure",
            unit="bytes",
            fields=[field("ZS", [("1h", "Empty"), ("Eh", "Full")])],
            source=Source(document="ZNS", figure_nr=38),
        ),
        Structure(
            name="Other",
            kind="data_structure",
            unit="bytes",
            fields=[field("OS", [("0h", "Empty")])],
            source=Source(document="ZNS", figure_nr=40),
        ),
    ]
    document.values = [
        Values(
            kind="other",
            columns=["value", "description"],
            entries=[
                Entry(value="1h", description="List the zones in the ZSE:Empty state."),
                Entry(value="5h", description="List the zones in the ZSF:Full state."),
                Entry(value="8h", name="Named", description="Of the ZSE:Empty state."),
            ],
            source=Source(document="ZNS", figure_nr=35),
        )
    ]
    link_named_values(document)

    links = [e.refers_to for e in document.values[0].entries]
    assert [(r.source.figure_nr, r.field, r.value, r.acronym) for r in links[:2]] == [
        (38, "ZS", "1h", "ZSE"),
        (38, "ZS", "Eh", "ZSF"),
    ]
    assert links[2] is None


def test_a_code_is_named_by_the_section_of_the_document_its_reference_names():
    """CNS 00h and 09h of Base 2.4 cite "NVM Express NVM Command Set
    Specification", whose sections titled "(CNS 00h)" and "(CNS 09h, CSI
    00h)" describe them; ZNS 1.5 cites it without "NVM Express". CNS 0Ah
    cites "I/O Command Set Specification", and two of the three command
    sets title its section alike. Neither code that one title of two names,
    nor one of a document without its section, nor one of no document, is
    named, nor 09h, whose title, but for the code, names 00h already."""

    from senfd.documents.spec import name_by_documents

    nvm = "NVM Express Foo Command Set Specification, Revision 1-3 Ratified 2026-07-31"
    zns = "NVM Express Zoned Foo Command Set Specification, Revision 1-5"
    kv = "NVM Express Key Foo Command Set Specification, Revision 1-4"
    merged = SpecDocument()
    merged.values = [
        cns_values(
            [
                ("01h", "5.1", False),
                ("00h", "NVM Express Foo Command Set Specification", False),
                # As ZNS 1.5 cites the NVM Command Set, without "NVM Express"
                ("09h", "Foo Command Set Specification", False),
                ("0Ah", "I/O Command Set Specification", False),
                ("0Bh", "NVM Express Foo Command Set Specification", False),
                ("0Ch", "I/O Command Set Specification", False),
                ("0Dh", "NVM Express Bar Specification", False),
            ]
        )
    ]
    merged.values[0].entries[0].name = "Identify Controller Data Structure"
    merged.sections = {
        "Base": {"5.1": SECTIONS["5.1"]},
        nvm: {
            "4.1": "Foo Identify Namespace Data Structure (CNS 00h)",
            "4.2": "Foo Identify Namespace Data Structure (CNS 09h, CSI 00h)",
            "4.3": "Foo Specific Namespace (CNS 0Ah, CSI 00h)",
            "4.4": "Foo Feature (Feature Identifier 0Bh)",
        },
        zns: {
            "4.3": "Foo specific Namespace (CNS 0Ah, CSI 02h)",
            "4.4": "Bar Namespace (CNS 0Ch, CSI 02h)",
        },
        kv: {
            "4.3": "Specific Foo Namespace (CNS 0Ah, CSI 01h)",
            "4.4": "Specific Foo Namespace (CNS 0Ch, CSI 01h)",
        },
    }
    name_by_documents(merged)
    assert [e.name for e in merged.values[0].entries] == [
        "Identify Controller Data Structure",
        "Foo Identify Namespace Data Structure",
        None,
        "Foo Specific Namespace",
        None,
        None,
        None,
    ]


def test_the_section_titles_of_each_document_are_kept_in_its_merge(tmp_path):
    """A merge names a code by a section of another document, so the spec
    document of each document keeps its section titles, and the merge those
    of every document"""

    spec = spec_of(Path("example") / "example.docx", tmp_path)
    assert spec.sections["example"]["1.2"] == "Ding command"
    assert merge([spec]).sections == spec.sections


def test_a_reference_to_a_number_two_sections_share_names_by_the_one_for_the_code():
    """The Base 2.4 PDF numbers the sections of CNS 14h and CNS 21h both
    5.2.14.3.1, and both codes cite it: each takes the section whose title
    names it, and neither is a candidate erratum"""

    from senfd.documents.spec import name_by_sections

    sections = SECTIONS | {
        "5.3": "Primary Controller Capabilities (CNS 14h)",
        "5.3 (2)": "Get Underlying Controller List (CNS 21h)",
    }
    document = SpecDocument()
    document.values.append(
        cns_values(
            [
                ("14h", "5.3", False),
                ("21h", "5.3", False),
                ("01h", "5.1", False),
                ("22h to 2Fh", "5.3", False),
            ]
        )
    )
    name_by_sections(document, sections)
    assert [e.name for e in document.values[0].entries] == [
        "Primary Controller Capabilities",
        "Get Underlying Controller List",
        "Identify Controller Data Structure",
        None,
    ]
    assert document.errata == []


def test_a_long_name_in_a_list_of_names_is_a_name():
    """Base 2.4 Figure 104 gives the status codes by name alone; a name of
    more than four words, as "Invalid Number of Controller Resources", reads
    as no name by itself, but the list it is in is of names. A range, and a
    list whose entries have descriptions, are left as they are."""

    from senfd.documents.spec import Entry, Source, Values, name_lists_of_names

    def values(*rows):
        return Values(
            kind="status_values",
            columns=["value", "description"],
            entries=[
                Entry(value=value, value_column="value", name=name, description=text)
                for value, name, text in rows
            ],
            source=Source(document="Base", figure_nr=104),
        )

    names = values(
        ("20h", "Invalid Secondary Controller State", ""),
        ("21h", None, "Invalid Number of Controller Resources"),
        ("22h", "Invalid Controller Identifier", ""),
        ("23h", None, "Sanitize Prohibited While Persistent Memory Region is Enabled"),
        ("80h to BFh", None, "I/O Command Set Specific or Fabrics Command Specific"),
    )
    described = values(
        ("01h", "Invalid Field", "A reserved field is set."),
        ("02h", None, "Invalid Number of Controller Resources"),
    )
    sentences = values(
        ("01h", "Foo", ""),
        ("02h", None, "The value is not supported by the controller."),
        ("03h", None, "Ignored by the Controller in Any State"),
    )
    document = SpecDocument(values=[names, described, sentences])
    name_lists_of_names(document)
    assert [e.name for e in names.entries] == [
        "Invalid Secondary Controller State",
        "Invalid Number of Controller Resources",
        "Invalid Controller Identifier",
        "Sanitize Prohibited While Persistent Memory Region is Enabled",
        None,
    ]
    assert names.entries[1].description == ""
    assert [e.name for e in described.entries] == ["Invalid Field", None]
    assert [e.name for e in sentences.entries] == ["Foo", None, None]


def test_an_array_ending_in_a_formula_has_the_maximum_its_figure_s_text_states():
    """ZNS 1.5 Figure 47 gives the last Zone Identifier as "Zone Identifier
    NZID-1", at a formula; the paragraph before it says the log page holds
    "up to 511 Zone Identifier entries", and Base 2.4 says "up to 511 Lost
    Host Communication Entries" of entries named in the singular"""

    from senfd.documents.spec import Array, Bits, maxima_of

    def entry(name, index):
        return Bits(
            name=f"{name} {index}",
            unit="bytes",
            range="15:08",
            role="field",
            kind="span",
            upper=15,
            lower=8,
            width=8,
            array=Array(name=name, index=index, first=0, stride=8, lower=8),
        )

    zones = [entry("Zone Identifier", 0), entry("Zone Identifier", None)]
    lost = [entry("Lost Host Communication Entry", 0)]
    counted = [entry("Foo", 0)]
    counted[0].array.count = 4
    maxima_of(
        zones + lost + counted,
        [
            "This log page contains a Zone Identifier List with up to 511 Zone "
            "Identifier entries. It is defined in Figure 47.",
            "A header followed by a list of up to 511 Lost Host Communication "
            "Entries, as in Figure 47.",
            "Up to 9 Foo entries.",
        ],
    )
    assert [f.array.maximum for f in zones + lost + counted] == [511, 511, 511, None]


def test_a_field_is_linked_to_the_structure_of_the_section_it_cites():
    """VER of Identify Controller "contains the value reported in the Version
    property (i.e., VS property) defined in section 3.1.4.2", where Figure 37
    lays out VS; it cites no figure"""

    def in_section(figure, section):
        figure.section = section
        return figure

    spec = document_of(
        in_section(
            figure_of(
                1,
                "Foo Register",
                ("Bits", "Description"),
                ("31:16", "Major (MJR): The major."),
                ("15:00", "Minor (MNR): The minor."),
            ),
            "3.1",
        ),
        in_section(
            figure_of(
                2,
                "Identify - Foo Data Structure",
                ("Bytes", "Description"),
                ("03:00", "Version (VER): The value of VS defined in section 3.1."),
                ("05:04", "Short (SH): A value defined in section 3.1."),
                ("09:08", "Domain (DID): Reported in the list of section 3.2."),
            ),
            "5.1",
        ),
        in_section(
            figure_of(
                3,
                "Command Dword 11 - Foo Specific Identifier",
                ("Bits", "Description"),
                ("15:00", "Domain (DID): The domain."),
            ),
            "3.2",
        ),
    )
    ver, short, domain = spec.structures[1].fields
    assert ver.structure is not None and ver.structure.figure_nr == 1
    assert short.structure is None
    # A structure of the field alone, as DID of a CNS Specific Identifier
    assert domain.structure is None


def test_a_field_is_linked_to_the_structure_its_name_captions_in_its_section():
    """CATTR of each range of NVM 1.3 Figure 47, in section 3.3.3, has no
    description; Figure 48 of section 3.3.3.2 lays out the "Dataset
    Management - Context Attributes" """

    def in_section(figure, section):
        figure.section = section
        return figure

    spec = document_of(
        in_section(
            figure_of(
                1,
                "Foo - Range Definition",
                ("Bytes", "Description"),
                ("03:00", "Context Attributes (CATTR)"),
                ("07:04", "Length (LEN)"),
            ),
            "3.3",
        ),
        in_section(
            figure_of(
                2,
                "Foo - Context Attributes",
                ("Bits", "Description"),
                ("31:08", "Size (SZ): The size."),
                ("07:00", "Flags (FL): The flags."),
            ),
            "3.3.2",
        ),
        in_section(
            figure_of(
                3,
                "Bar - Length",
                ("Bits", "Description"),
                ("31:00", "Length (LEN): The length."),
            ),
            "4.1",
        ),
    )
    cattr, length = spec.structures[0].fields
    assert cattr.structure is not None and cattr.structure.figure_nr == 2
    assert length.structure is None


def test_a_case_by_a_field_of_another_figure_has_the_numbers_of_its_codes():
    """The cases of DPTR of Base 2.4 Figure 93 are by PSDT of CDW0, which
    another figure lays out; "00b", "01b" and "10b" are codes"""

    from senfd.tables import Cell, Table

    def table(*texts):
        from senfd.tables import Row

        return Table(rows=[Row(cells=[Cell(text=t) for t in row]) for row in texts])

    described = Cell(
        text=(
            "Data Pointer (DPTR): The data.\n"
            "If CDW0.PSDT is cleared to 00b, then the definition of this field is:\n"
            "If CDW0.PSDT is set to 01b or 10b, then the definition of this field is:"
        ),
        tables=[
            table(
                ("39:32", "PRP Entry 2 (PRP2): The second."),
                ("31:24", "PRP Entry 1 (PRP1): The first."),
            ),
            table(("39:24", "SGL Entry 1 (SGL1): The first segment.")),
        ],
    )
    spec = document_of(
        figure_of(
            1,
            "Foo Command Format",
            ("Bytes", "Description"),
            ("23:00", "Foo (F): Foo."),
            ("39:24", described),
        )
    )
    dptr = spec.structures[0].fields[1]
    assert [
        (c.selector, [(w.name, w.value) for w in c.when], [f.acronym for f in c.fields])
        for c in dptr.cases
    ] == [
        ("PSDT", [("00b", 0)], ["PRP2", "PRP1"]),
        ("PSDT", [("01b", 1), ("10b", 2)], ["SGL1"]),
    ]


def test_a_figure_a_description_gives_as_an_example_lays_out_nothing_of_it():
    """PRP1 of the Common Command Format is "the first PRP entry for the
    command; or a PRP List pointer, depending on the command (e.g., the
    Create I/O Completion Queue command (refer to Figure 571))": the PRP
    Entry 1 of that one command"""

    spec = document_of(
        figure_of(
            1,
            "Foo Command Format",
            ("Bytes", "Description"),
            (
                "07:00",
                "PRP Entry 1 (PRP1): The first PRP entry, depending on the "
                "command (e.g., the Create Foo command (refer to Figure 2)).",
            ),
            ("15:08", "Bar Entry (BE): The entry as in Figure 2."),
        ),
        figure_of(
            2,
            "Create Foo - PRP Entry 1",
            ("Bits", "Description"),
            ("63:12", "Base (BASE): The base."),
            ("11:00", "Reserved"),
        ),
    )
    prp1, bar = spec.structures[0].fields
    assert prp1.structure is None
    assert bar.structure is not None and bar.structure.figure_nr == 2


def test_a_field_citing_a_section_of_several_formats_is_linked_to_the_general():
    """SGL1 of the Common Command Format cites "section 4.3.2", which lays out
    the Generic SGL Descriptor Format, Base 2.4 Figure 116, and six SGL
    descriptors as wide, each of which divides the bytes the generic format
    divides"""

    def in_section(figure, section):
        figure.section = section
        return figure

    spec = document_of(
        in_section(
            figure_of(
                1,
                "Generic Foo Descriptor Format",
                ("Bytes", "Description"),
                ("14:00", "Descriptor Type Specific (DTS): Specific."),
                ("15", "Foo Identifier (FID): The type."),
            ),
            "4.3",
        ),
        in_section(
            figure_of(
                2,
                "Foo Data Block descriptor",
                ("Bytes", "Description"),
                ("07:00", "Address (ADDR): The address."),
                ("14:08", "Length (LEN): The length."),
                ("15", "Foo Identifier (FID): The type."),
            ),
            "4.3",
        ),
        in_section(
            figure_of(
                3,
                "Foo Segment descriptor",
                ("Bytes", "Description"),
                ("07:00", "Address (ADDR): The address."),
                ("10:08", "Length (LEN): The length."),
                ("14:11", "Key (KEY): The key."),
                ("15", "Foo Identifier (FID): The type."),
            ),
            "4.3",
        ),
        in_section(
            figure_of(
                4,
                "Foo Command Format",
                ("Bytes", "Description"),
                (
                    "15:00",
                    "Foo Entry 1 (FOO1): Refer to section 4.3 for the descriptors.",
                ),
            ),
            "5.1",
        ),
    )
    (foo1,) = spec.structures[3].fields
    assert foo1.structure is not None and foo1.structure.figure_nr == 1


def test_a_numbered_field_is_linked_to_the_structure_its_name_captions():
    """PRP1 and PRP2 of the Common Command Format are "PRP Entry 1" and "PRP
    Entry 2", and Base 2.4 Figure 111 is "PRP Entry - Page Base Address and
    Offset"; neither description cites it"""

    spec = document_of(
        figure_of(
            1,
            "Bar Entry - Page Base Address and Offset",
            ("Bits", "Description"),
            ("63:00", "Page Base Address and Offset (PBAO): The address."),
        ),
        figure_of(
            2,
            "Foo Command Format",
            ("Bytes", "Description"),
            ("07:00", "Bar Entry 1 (BAR1): The first entry for the command."),
            ("15:08", "Bar Entry 2 (BAR2): The second entry."),
            ("19:16", "Bar Entry 3 (BAR3): Narrower than an entry."),
            ("21:20", "Foo Identifier 0: The first."),
        ),
        figure_of(
            3,
            "Foo Identifier - Log Specific Identifier",
            ("Bits", "Description"),
            ("15:00", "Foo Identifier (FID): The identifier."),
        ),
    )
    bar1, bar2, bar3, foo0 = spec.structures[1].fields
    assert bar1.structure is not None and bar1.structure.figure_nr == 1
    assert bar2.structure is not None and bar2.structure.figure_nr == 1
    assert bar3.structure is None
    # A structure of the field alone, as the Controller Identifier - Log
    # Specific Identifier for an entry of the Controller List
    assert foo0.structure is None


def test_a_field_referring_to_a_figure_has_the_link_of_the_field_there():
    """SGL1 of Authentication Receive, Base 2.4 Figure 631, says only "Refer
    to Figure 95.", the Fabrics Command SQE, whose SGL1 is at the same bytes"""

    spec = document_of(
        figure_of(
            1,
            "Foo Descriptor",
            ("Bytes", "Description"),
            ("07:00", "Address (ADDR): The address."),
            ("15:08", "Length (LEN): The length."),
        ),
        figure_of(
            2,
            "Foo Command SQE",
            ("Bytes", "Description"),
            ("23:00", "Other (OTH): Other."),
            ("39:24", "Foo Entry 1 (FOO1): A Foo Descriptor as in Figure 1."),
        ),
        figure_of(
            3,
            "Foo Receive Command SQE",
            ("Bytes", "Description"),
            ("23:00", "Other (OTH): Refer to Figure 2."),
            ("39:24", "Foo Entry 1 (FOO1): Refer to Figure 2."),
        ),
        figure_of(
            4,
            "Bar List",
            ("Bytes", "Description"),
            ("15:00", "Bar Record 0: The first, as in Figure 5."),
        ),
        figure_of(
            5,
            "Foo List",
            ("Bytes", "Description"),
            ("15:00", "Foo Descriptor 0: A Foo Descriptor as in Figure 1."),
            ("31:16", "Foo Descriptor 1: A Foo Descriptor as in Figure 1."),
        ),
    )
    other, foo1 = spec.structures[2].fields
    assert foo1.structure is not None and foo1.structure.figure_nr == 1
    assert other.structure is None
    # A field without an acronym is no field of the figure referred to
    (foo0,) = spec.structures[3].fields
    assert foo0.structure is None


def selections_document():
    """Base with a CNS table and a table of Command Set Identifiers, and two
    command set documents, each with its own CNS table"""

    from senfd.documents.spec import Entry, Source, Structure, Values

    base = "NVM Express Base Specification, Revision 2-4"
    foo = "NVM Express Foo Command Set Specification, Revision 1-3"
    bar = "NVM Express Bar Command Set Specification, Revision 1-4"

    def structure(document, figure_nr, section, name, kind="data_structure"):
        return Structure(
            name=name,
            kind=kind,
            unit="bytes",
            source=Source(document=document, figure_nr=figure_nr, section=section),
        )

    def cns(document, figure_nr, rows):
        return Values(
            kind="cns_values",
            name="Identify",
            columns=["cns_value", "description", "reference", "csi"],
            entries=[
                Entry(
                    value=value,
                    value_column="cns_value",
                    columns={"reference": reference, "csi": csi},
                )
                for value, reference, csi in rows
            ],
            source=Source(document=document, figure_nr=figure_nr),
        )

    document = SpecDocument()
    document.structures = [
        structure(base, 338, "5.1", "Identify Controller"),
        structure(base, 339, "5.1", "Power State Descriptor"),
        structure(base, 333, "5.1", "Identify - Command Dword 10", "command_dword"),
        structure(foo, 123, "4.1", "Identify Namespace"),
        structure(foo, 127, "4.2", "Foo Specific Identify Namespace (CSI 00h)"),
        structure(bar, 42, "5.2", "Bar Specific Identify Namespace"),
    ]
    document.values = [
        cns(
            base,
            336,
            [
                ("01h", "5.1", "N"),
                ("00h", "NVM Express Foo Command Set Specification", "N"),
                ("05h", "5.9", "Y"),
                ("07h", "5.8", "N"),
            ],
        ),
        Values(
            kind="other",
            name="Command Set Identifiers",
            columns=["value", "command_set"],
            entries=[
                Entry(value="00h", value_column="value", name="Foo Command Set"),
                Entry(value="01h", value_column="value", name="Bar Command Set"),
                Entry(value="02h", value_column="value", name="Baz Command Set"),
            ],
            source=Source(document=base, figure_nr=337),
        ),
        cns(foo, 122, [("00h", "4.1", "N"), ("05h", "4.2", "Y")]),
        cns(bar, 41, [("05h", "5.2", "Y")]),
    ]
    return document, base, foo, bar


def test_a_cns_value_selects_the_structures_of_the_section_its_reference_cites():
    """CNS 01h of Base 2.4 Figure 336 cites section 5.2.13.2.1, which lays
    out the Identify Controller data structure and its Power State
    Descriptor; the dwords of the Identify command are no structure it
    selects"""

    from senfd.documents.spec import link_selections

    document, base, foo, bar = selections_document()
    link_selections(document)
    by_value = {e.value: e for e in document.values[0].entries}
    assert [s.figure_nr for s in by_value["01h"].selects] == [338, 339]
    # A section without a structure
    assert by_value["07h"].selects == []


def test_a_cns_value_selects_the_structures_of_the_same_value_in_a_document_it_cites():
    """CNS 00h of Base 2.4 cites the NVM Command Set Specification, whose
    own CNS 00h cites its section of the Identify Namespace data structure"""

    from senfd.documents.spec import link_selections

    document, base, foo, bar = selections_document()
    link_selections(document)
    by_value = {e.value: e for e in document.values[0].entries}
    assert [(s.document, s.figure_nr) for s in by_value["00h"].selects] == [(foo, 123)]


def test_a_cns_value_the_csi_selects_has_the_structures_of_each_command_set():
    """CNS 05h of Base 2.4 is "I/O Command Set specific Identify Namespace",
    with Y in its CSI column, and Base has no structure of it; each command
    set that the Command Set Identifiers of Figure 337 name has its own"""

    from senfd.documents.spec import link_selections

    document, base, foo, bar = selections_document()
    link_selections(document)
    csis = document.values[1].entries
    assert [e.document for e in csis] == [foo, bar, None]
    by_value = {e.value: e for e in document.values[0].entries}
    assert [(s.document, s.figure_nr) for s in by_value["05h"].selects] == [
        (foo, 127),
        (bar, 42),
    ]
    # The command sets' own CNS 05h select their own structure only
    assert [s.figure_nr for s in document.values[2].entries[1].selects] == [127]


def test_a_command_has_the_tables_of_status_values_its_name_captions():
    """Base 2.4 Figure 331, "Get Log Page - Command Specific Status Values",
    gives the status values of Get Log Page"""

    from senfd.documents.spec import (
        Command,
        CommandSet,
        Source,
        Values,
        link_selections,
    )

    document = SpecDocument()
    document.command_sets = {
        "admin": CommandSet(
            name="Admin",
            commands={
                "get_log_page": Command(
                    name="Get Log Page",
                    opcode=2,
                    source=Source(document="Base", figure_nr=1),
                ),
                "identify": Command(
                    name="Identify",
                    opcode=6,
                    source=Source(document="Base", figure_nr=1),
                ),
                "foo_zoning_lookup": Command(
                    name="Foo Zoning Lookup",
                    opcode=7,
                    source=Source(document="Base", figure_nr=1),
                ),
            },
        )
    }
    document.values = [
        Values(
            kind="status_values",
            name="Get Log Page",
            source=Source(document="Base", figure_nr=331),
        ),
        Values(
            kind="status_values",
            name="Generic Command",
            source=Source(document="Base", figure_nr=104),
        ),
        # As "Fabric Zoning Lookup (FZL) - Command Specific Status Values"
        Values(
            kind="status_values",
            name="Foo Zoning Lookup (FZL)",
            source=Source(document="Base", figure_nr=604),
        ),
    ]
    link_selections(document)
    commands = document.command_sets["admin"].commands
    assert [s.figure_nr for s in commands["get_log_page"].status_values] == [331]
    assert commands["identify"].status_values == []
    assert [s.figure_nr for s in commands["foo_zoning_lookup"].status_values] == [604]


def test_a_command_has_each_status_value_whose_commands_affected_name_it():
    """Base 2.4 Figure 104 gives 00h, Completion Queue Invalid, for Create
    I/O Submission Queue; ZNS 1.5 Figure 11 names Read, a command of NVM
    1.3 alone, with the footnote marker of "Read1" """

    from senfd.documents.spec import (
        Command,
        CommandSet,
        Entry,
        Source,
        ValueLink,
        Values,
        link_selections,
    )

    def command(name, document):
        return Command(
            name=name, opcode=1, source=Source(document=document, figure_nr=1)
        )

    document = SpecDocument()
    document.command_sets = {
        "admin": CommandSet(
            name="Admin",
            commands={"create": command("Create I/O Submission Queue", "Base")},
        ),
        "nvm": CommandSet(
            name="NVM",
            commands={"read": command("Read", "NVM"), "write": command("Write", "NVM")},
        ),
        "kv": CommandSet(name="KV", commands={"read": command("Read", "KV")}),
    }
    base = Source(document="Base", figure_nr=104)
    zns = Source(document="ZNS", figure_nr=11)
    document.values = [
        Values(
            kind="status_values",
            name="Status Code",
            source=base,
            entries=[
                Entry(
                    value="00h",
                    name="Completion Queue Invalid",
                    columns={"commands_affected": "Create I/O Submission Queue"},
                ),
                Entry(value="01h", columns={"commands_affected": "NOTE 1"}),
            ],
        ),
        Values(
            kind="status_values",
            name="Status Code",
            source=zns,
            entries=[
                Entry(value="B8h", columns={"commands_affected": "Read1, Write"}),
            ],
        ),
    ]
    link_selections(document)
    commands = document.command_sets

    assert commands["admin"].commands["create"].status_codes == [
        ValueLink(source=base, field="Status Code", value="00h")
    ]
    linked = [ValueLink(source=zns, field="Status Code", value="B8h")]
    assert commands["nvm"].commands["write"].status_codes == linked
    # Read is a command of NVM and of KV, so the ZNS table links neither,
    # and an NVM table links the Read of NVM
    assert commands["nvm"].commands["read"].status_codes == []
    nvm = Source(document="NVM", figure_nr=19)
    document.values.append(
        Values(
            kind="status_values",
            name="Status Code",
            source=nvm,
            entries=[Entry(value="80h", columns={"commands_affected": "Read"})],
        )
    )
    link_selections(document)
    own = [ValueLink(source=nvm, field="Status Code", value="80h")]
    assert commands["nvm"].commands["read"].status_codes == own
    assert commands["kv"].commands["read"].status_codes == []
    document.values.pop()
    del commands["kv"]
    link_selections(document)
    assert commands["nvm"].commands["read"].status_codes == linked


def test_a_case_selected_by_a_field_of_another_figure_links_that_figure():
    """DPTR of Base 2.4 Figure 93 has cases by "CDW0.PSDT", and CDW0 of
    Figure 93 is laid out by Figure 92, which has PSDT"""

    from senfd.documents.spec import (
        Bits,
        Case,
        Selected,
        Source,
        Structure,
        link_selectors,
    )

    def bits(acronym, unit="bits", **more):
        return Bits(
            unit=unit,
            upper=1,
            lower=0,
            range="1:0",
            acronym=acronym,
            name=acronym,
            role="field",
            kind="span",
            width=2,
            **more,
        )

    def structure(figure_nr, fields):
        return Structure(
            name=f"Figure {figure_nr}",
            kind="data_structure",
            unit="bytes",
            source=Source(document="Base", figure_nr=figure_nr),
            fields=fields,
        )

    cdw0 = structure(92, [bits("PSDT"), bits("OPC")])
    by = [Case(selector="PSDT", when=[Selected(name="00b", value=0)])]
    own = [Case(selector="OPC", when=[Selected(name="00b", value=0)])]
    unlinked = [Case(selector="PSDT", when=[Selected(name="00b", value=0)])]
    common = structure(
        93,
        [
            bits("CDW0", unit="bytes", structure=cdw0.source),
            bits("OPC"),
            bits("DPTR", description="If CDW0.PSDT is cleared to 00b", cases=by),
            bits("MPTR", description="If OPC is 00b", cases=own),
            bits("CDW2", description="If CDW3.PSDT is 00b", cases=unlinked),
        ],
    )
    document = SpecDocument()
    document.structures = [cdw0, common]
    link_selectors(document)

    assert by[0].selector_in == cdw0.source
    # OPC is a field of the case's own figure, and CDW3 is none
    assert own[0].selector_in is None
    assert unlinked[0].selector_in is None


def test_a_log_page_is_one_by_identifier_named_by_the_table_of_identifiers():
    """Base 2.4 Figure 209 names log page 24h "Manufacturer Default
    Configuration" and Figure 31 "... Status"; Figure 31 also lists 02h once
    by scope. A log page is one by identifier, named by Figure 209, with the
    other name and the columns of Figure 31 added. Its structure is the
    figure its row's reference section holds that is named as the log page,
    as the one of 12h, whose figure is named otherwise."""

    requirements = figure_of(
        31,
        "Log Page Support Requirements",
        ("Log Page Name", "Log Page Identifier", "I/O", "Reference"),
        ("Foo Information (Controller scope)", "02h", "M", "5.1"),
        ("Foo Information (Namespace scope)", "02h", "O", "5.1"),
        ("Bar Default Configuration Status", "24h", "O", "5.2"),
    )
    identifiers = figure_of(
        209,
        "Get Log Page - Log Page Identifiers",
        ("Log Page Identifier", "Scope", "Log Page Name", "Reference Section"),
        ("02h", "Controller", "Foo Information", "5.1"),
        ("12h", "Controller", "Baz Identifiers Supported and Effects", "5.3"),
        ("24h", "Controller", "Bar Default Configuration", "5.2"),
    )
    layouts = [
        figure_of(300, f"{name} Log Page", ("Bytes", "Description"), *rows)
        for name, rows in (
            ("Foo Information", [("00", "Foo (FOO): The foo.")]),
            ("Bar Extended Default", [("00", "Ext (EXT): The extended.")]),
            ("Bar Default Configuration Status", [("00", "Bar (BAR): The bar.")]),
            ("Baz Effects", [("00", "Baz (BAZ): The baz.")]),
        )
    ]
    for layout, number, section in zip(layouts, (301, 302, 303, 304), "1223"):
        layout.figure_nr, layout.section = number, f"5.{section}"
        layout.caption = layout.caption.replace("Figure 300", f"Figure {number}")
    spec = document_of(requirements, identifiers, *layouts)

    pages = {page.identifier: page for page in spec.log_pages.values()}
    assert len(spec.log_pages) == 3
    assert pages[0x02].name == "Foo Information"
    assert pages[0x02].columns["i_o"] == "M"
    assert pages[0x24].name == "Bar Default Configuration"
    assert pages[0x24].aliases == ["Bar Default Configuration Status"]
    assert pages[0x24].structure.source.figure_nr == 303
    assert pages[0x12].structure.name == "Baz Effects"


def test_two_structures_of_one_name_are_told_apart_by_kind_or_linking_field():
    """Base 2.4 Figures 216 and 217 are the log page and the data structure
    "Commands Supported and Effects"; NVM 1.3 Figure 190 has the caption of
    Figure 189 and is the layout of RENSCS"""

    spec = document_of(
        figure_of(
            216,
            "Foo Effects Log Page",
            ("Bytes", "Description"),
            ("00", "Foo (FOO): The foo."),
        ),
        figure_of(
            217,
            "Foo Effects Data Structure",
            ("Bits", "Description"),
            ("0", "Bar (BAR): The bar."),
        ),
        figure_of(
            183,
            "Reference State",
            ("Bytes", "Description"),
            ("03:00", "Reference Controller State (RCS): Refer to Figure 189."),
            ("07:04", "Reference Namespace State (RNS): Refer to Figure 190."),
        ),
        figure_of(
            189,
            "Reference Controller State",
            ("Bytes", "Description"),
            ("03:00", "Ding (DING): A ding."),
        ),
        figure_of(
            190,
            "Reference Controller State",
            ("Bytes", "Description"),
            ("03:00", "Ring (RING): A ring."),
        ),
    )
    names = {s.source.figure_nr: s.name for s in spec.structures}
    assert names[216] == "Foo Effects"
    assert names[217] == "Foo Effects Data Structure"
    assert names[189] == "Reference Controller State"
    assert names[190] == "Reference Namespace State"
    (erratum,) = [e for e in spec.errata if e.code == "caption"]
    assert erratum.source.figure_nr == 190


def test_a_numbered_field_of_another_width_and_a_size_past_a_power_of_two_are_errata():
    """Boot 1.4 Figure 11 gives Host Fabric Interface Descriptor 2 the
    bytes 64:32, 33 bytes, between descriptors of 32; NVM 1.3 Figure 134
    ends in "4096:768 Reserved", 4097 bytes"""

    spec = document_of(
        figure_of(
            11,
            "Foo Descriptor List",
            ("Bytes", "Description"),
            ("31:00", "Foo Descriptor 1: The first."),
            ("64:32", "Foo Descriptor 2: The second."),
            ("(n*32)-1:(n-1)*32", "Foo Descriptor n: The last."),
        ),
        figure_of(
            134,
            "Foo Data Structure",
            ("Bytes", "Description"),
            ("767:00", "Foo (FOO): The foo."),
            ("4096:768", "Reserved"),
        ),
    )
    found = sorted(
        (e.source.figure_nr, e.found) for e in spec.errata if e.code == "range"
    )
    assert found == [(11, "64:32"), (134, "4096:768")]


def test_a_layout_of_another_kind_from_byte_0_has_its_gaps_reported():
    """SLM 1.3 Figure 13 lays out source range entries; its second entry has
    no row for bytes 53:52. A table whose rows name the structure of each
    field, as NVM 1.3 Figure 188, cites fields of others, and has none."""

    spec = document_of(
        figure_of(
            13,
            "Foo Entries for Format 4h",
            ("Bytes", "Description"),
            ("03:00", "Foo (FOO): The foo."),
            ("07:06", "Bar (BAR): The bar."),
        ),
        figure_of(
            188,
            "Reference Foo Structures",
            ("Data Structure", "Bytes", "Description"),
            ("Foo", "03:00", "Foo (FOO): The foo."),
            ("Bar", "519:516", "Number of Bars (NB): The bars."),
        ),
    )
    (gap,) = [e for e in spec.errata if e.code == "layout-gap"]
    assert gap.source.figure_nr == 13
    kinds = {s.source.figure_nr: s.kind for s in spec.structures}
    assert kinds == {13: "other", 188: "cited_fields"}


def test_the_one_row_of_no_name_of_a_register_is_the_register():
    """CCPTR of PCIe 1.4 Figure 23 has one row, "31:00 RO 0h Shall be
    cleared to zero for NVM Express use", and no field otherwise"""

    spec = document_of(
        figure_of(
            23,
            "Offset 28h: FPTR - Foo Pointer",
            ("Bits", "Type", "Reset", "Description"),
            ("31:00", "RO", "0h", "Shall be cleared to zero for NVM Express use."),
        )
    )
    (register,) = spec.structures
    assert [(f.range, f.name, f.acronym) for f in register.fields] == [
        ("31:00", "Foo Pointer", "FPTR")
    ]


def test_fields_numbered_in_hexadecimal_with_rows_left_out_are_an_array():
    """NVM 1.3 Figure 104 lists Performance Attribute C1h, C2h, "..." and FFh
    Identifier; Base 2.4 Figure 516 lists Vendor Specific Protocol FF, F1,
    "..." and F0, the acronyms VSPFF to VSPF0 in SPS and VSP15 to VSP0 in
    SSP, and gives AHATSDPS to two fields"""

    from senfd.documents.spec import Array

    spec = document_of(
        figure_of(
            104,
            "Foo Identifier List",
            ("Bytes", "Description"),
            ("15:00", "Reserved"),
            ("31:16", "Foo Attribute C1h Identifier (FAC1HI): The first."),
            ("47:32", "Foo Attribute C2h Identifier (FAC2HI): The second."),
            ("...", ""),
            ("1023:1008", "Foo Attribute FFh Identifier (FACFFHI): The last."),
        ),
        figure_of(
            516,
            "Bar Data Structure",
            ("Bits", "Description"),
            ("31", "Bar Protocol FF (BPFF): The last."),
            ("...", ""),
            ("17", "Bar Protocol F1 (BPF1): The second."),
            ("16", "Bar Protocol F0 (BPF0): The first."),
            ("15:03", "Reserved"),
            ("02", "Bar Protocol Status (BPS): The status."),
            ("01", "Bar Protocol Support (BPS): The support."),
            ("00", "Reserved"),
        ),
        figure_of(
            517,
            "Baz Data Structure",
            ("Bits", "Description"),
            ("31", "Baz Protocol FF (BZP15): The last."),
            ("...", ""),
            ("17", "Baz Protocol F1 (BZP1): The second."),
            ("16", "Baz Protocol F0 (BZP0): The first."),
            ("15:00", "Reserved"),
        ),
    )
    foo, bar, baz = spec.structures
    assert foo.fields[-1].array == Array(
        name="Foo Attribute Identifier",
        index=255,
        first=193,
        count=63,
        stride=16,
        lower=16,
    )
    assert bar.fields[0].array == Array(
        name="Bar Protocol",
        acronym="BP",
        index=255,
        first=240,
        count=16,
        stride=1,
        lower=16,
    )
    assert [f.array.index for f in baz.fields[:3]] == [255, 241, 240]
    assert sorted((e.source.figure_nr, e.code, e.found) for e in spec.errata) == [
        (516, "acronym", "BPS"),
        (517, "acronym", ""),
    ]


def test_a_layout_of_bytes_of_another_structure_extends_it():
    """NVM 1.3 Figure 126 lays out AWUN, AWUPF and ACWU, bytes 527:526 to
    533:532 of Identify Controller, Base 2.4 Figure 338, which has them
    too; MI 2.2 Figure 41 lays out bytes 07:06, which the text calls "the
    CPSR field in the Control Primitive Success Response", of Figure 40"""

    from senfd.documents.spec import resolve

    base = document_of(
        figure_of(
            338,
            "Foo Controller Data Structure",
            ("Bytes", "Description"),
            ("01:00", "Foo Identifier (FID)"),
            ("03:02", "Foo Write Unit (FWU)"),
            ("07:04", "Foo Atomic Unit (FAU)"),
        ),
        stem="base",
    )
    figure = figure_of(
        41,
        "Pause Foo Response Fields",
        ("Bytes", "Description"),
        ("07:06", "Pause Flags (PFL)"),
    )
    figure.mentions = [
        "The format of the FSR field in the Foo Response is shown in Figure 41."
    ]
    command_set = document_of(
        figure_of(
            126,
            "Foo Controller Data Structure",
            ("Bytes", "Description"),
            ("03:02", "Foo Write Unit (FWU): For this command set."),
            ("07:04", "Foo Atomic Unit (FAU): For this command set."),
        ),
        figure_of(
            40,
            "Foo Response Fields",
            ("Bytes", "Description"),
            ("05:00", "Reserved"),
            ("07:06", "Foo Specific Response (FSR)"),
        ),
        figure,
        stem="nvm",
    )
    command_set.structures += base.structures
    resolved = resolve(command_set)
    extends = {
        s.source.figure_nr: (s.extends and s.extends.figure_nr, s.extends_field)
        for s in resolved.structures
    }
    assert extends == {
        126: (338, None),
        40: (None, None),
        41: (40, "FSR"),
        338: (None, None),
    }


def test_the_encoding_and_byte_order_a_description_states_are_the_fields():
    """FR of Identify Controller, Base 2.4 Figure 338, is "the currently
    active firmware revision, as an ASCII string", and FGUID "is big
    endian"; FR of NVM 1.3 Figure 189 has "the value of the FR field in the
    Identify Controller data structure" """

    spec = document_of(
        figure_of(
            338,
            "Identify Foo Controller Data Structure",
            ("Bytes", "Description"),
            ("07:00", "Foo Revision (FR): The revision, as an ASCII string."),
            ("23:08", "Foo Unique Identifier (FGUID): This field is big endian."),
            ("39:24", "Foo Name (FNAME): A UTF-8 null-terminated string."),
            (
                "55:40",
                "Foo Identity (FUUID): A 128-bit Universally Unique Identifier (UUID).",
            ),
            ("63:56", "Foo Count (FCNT): The count."),
        ),
        figure_of(
            189,
            "Foo Reference Data Structure",
            ("Bytes", "Description"),
            (
                "07:00",
                "Foo Revision (FR): The value of the FR field in the Identify Foo Controller data structure.",
            ),
            (
                "23:08",
                "Foo Unique Identifier (FGUID): The value of the FGUID field in the Identify Foo Controller data structure.",
            ),
        ),
    )
    found = [
        [(f.acronym, f.encoding, f.byte_order) for f in s.fields]
        for s in spec.structures
    ]
    assert found == [
        [
            ("FR", "ascii", None),
            ("FGUID", None, "big-endian"),
            ("FNAME", "utf-8", None),
            ("FUUID", "uuid", None),
            ("FCNT", None, None),
        ],
        [("FR", "ascii", None), ("FGUID", None, "big-endian")],
    ]


def test_a_short_definition_names_its_value_and_a_title_names_one_code_only():
    """AET of Base 2.4 lists 000b "Error status" beside 010b "Notice", and
    NVM 1.3 titles the sections of CNS 00h and CNS 09h alike, "NVM Command
    Set Identify Namespace Data Structure" """

    from senfd.documents.spec import name_by_sections, name_lists_of_names
    from senfd.tables import Cell, Row, Table

    values = Table(
        rows=[
            Row(cells=[Cell(text=t) for t in row])
            for row in (
                ("Value", "Definition"),
                ("000b", "Error status"),
                ("001b", "Notice"),
                ("010b", "One or more of the logical blocks are allocated."),
                ("011b to 111b", "Reserved"),
            )
        ]
    )
    described = Cell(text="Foo Event Type (FET): The type.", tables=[values])
    document = SpecDocument()
    from senfd.documents.normalized import normalize_figure
    from senfd.documents.spec import add_figure

    figure = figure_of(
        1, "Foo Data Structure", ("Bits", "Description"), ("02:00", described)
    )
    add_figure(document, normalize_figure(figure, []), "example")
    name_lists_of_names(document)
    (field,) = document.structures[0].fields
    assert [(v.value, v.name) for v in field.values] == [
        ("000b", "Error status"),
        ("001b", "Notice"),
        ("010b", None),
        ("011b to 111b", "Reserved"),
    ]

    document = SpecDocument()
    document.values.append(cns_values([("00h", "5.1", False), ("09h", "5.2", False)]))
    name_by_sections(
        document,
        {
            "5.1": "Foo Identify Namespace Data Structure (CNS 00h)",
            "5.2": "Foo Identify Namespace Data Structure (CNS 09h, CSI 00h)",
        },
    )
    assert [e.name for e in document.values[0].entries] == [
        "Foo Identify Namespace Data Structure",
        None,
    ]


def test_a_run_listed_in_full_and_groups_of_rows_named_by_index_are_arrays():
    """TSEN1 to TSEN8 of the SMART / Health Information log page are listed
    one by one; NVM 1.3 Figure 40 names its groups of rows "Source Range 0"
    to "Source Range 127" in a column of their own"""

    from senfd.documents.spec import Array

    spec = document_of(
        figure_of(
            213,
            "Foo Health Data Structure",
            ("Bytes", "Description"),
            ("01:00", "Foo Sensor 1 (FSEN1): The first."),
            ("03:02", "Foo Sensor 2 (FSEN2): The second."),
            ("05:04", "Foo Sensor 3 (FSEN3): The third."),
            ("07:06", "Bar Mode 1 (BM1): One."),
            ("09:08", "Bar Mode 2 (BM2): Two."),
        ),
        figure_of(
            40,
            "Foo Range Entries",
            ("Range", "Bytes", "Description"),
            ("Foo Range 0", "07:00", "Foo Start (FST): The start."),
            ("", "15:08", "Foo Length (FLEN): The length."),
            ("Foo Range 1", "23:16", "Foo Start (FST): The start."),
            ("Foo Range 1", "31:24", "Foo Length (FLEN): The length."),
            ("...", "", ""),
            ("Foo Range 3", "55:48", "Foo Start (FST): The start."),
            ("Foo Range 3", "63:56", "Foo Length (FLEN): The length."),
        ),
    )
    health, ranges = spec.structures
    assert health.fields[2].array == Array(
        name="Foo Sensor", acronym="FSEN", index=3, first=1, count=3, stride=2, lower=0
    )
    assert health.fields[3].array is None
    assert [f.group.index for f in ranges.fields] == [0, 0, 1, 1, 3, 3]
    assert ranges.fields[0].group == Array(
        name="Foo Range", index=0, first=0, count=4, stride=16, lower=0
    )


def test_each_entry_of_a_run_links_the_structure_one_of_them_links():
    """SC Entry 0 of Base 2.4 Figure 361 is "defined in Figure 362" and SC
    Entry 1 cites nothing; Subsystem Namespace Descriptor n of Boot 1.4
    Figure 16 cites Figure 9 for the field that counts the descriptors"""

    spec = document_of(
        figure_of(
            9,
            "Foo Table",
            ("Bytes", "Description"),
            ("63:00", "Number of Foo Entries (NFE): The count."),
        ),
        figure_of(
            361,
            "Foo List",
            ("Bytes", "Description"),
            ("63:00", "Foo Entry 0: The first, defined in Figure 362."),
            ("127:64", "Foo Entry 1: The second, if present."),
            (
                "(n*64)-1:(n-1)*64",
                "Foo Entry n: The last, n is NFE (refer to Figure 9).",
            ),
        ),
        figure_of(
            362,
            "Foo Entry",
            ("Bytes", "Description"),
            ("63:00", "Foo Value (FV): The value."),
        ),
    )
    (listing,) = [s for s in spec.structures if s.source.figure_nr == 361]
    assert [f.structure and f.structure.figure_nr for f in listing.fields] == [362] * 3


def test_dwords_in_a_section_titled_with_a_code_are_an_operation_selected_by_it():
    """MI 2.2 lays out the Management Dword 0 of Configuration Get for each
    configuration in a section titled "SMBus/I2C Frequency (Configuration
    Identifier 01h)"; Base 2.4 Figure 343, "Command Dword 11 - CNS Specific
    Identifier" in "NVM Set List (CNS 04h)", names a field of Identify, and
    Figure 352 is in "Endurance Group List (19h)" """

    def placed(figure, section, title):
        figure.section, figure.section_title = section, title
        return figure

    spec = document_of(
        figure_of(
            1,
            "Opcodes for Admin Commands",
            OPCODES,
            ("00b", "00b", "10h", "Foo Get", "5.1"),
            ("00b", "10b", "11h", "Foo Identify", "5.2"),
        ),
        placed(
            figure_of(
                2,
                "Foo Get - Command Dword 10",
                ("Bits", "Description"),
                ("31:08", "Reserved"),
                ("07:00", "Configuration Identifier (CID): The configuration."),
            ),
            "5.1",
            "Foo Get command",
        ),
        placed(
            figure_of(
                3,
                "Foo Frequency - Command Dword 11",
                ("Bits", "Description"),
                ("31:00", "Frequency (FREQ): The frequency."),
            ),
            "5.1.1",
            "Foo Frequency (Configuration Identifier 01h)",
        ),
        placed(
            figure_of(
                4,
                "Foo Identify - Command Dword 11",
                ("Bits", "Description"),
                ("31:24", "Command Set Identifier (CSI): The set."),
                ("23:08", "CNS Specific Identifier (CNSSID): The identifier."),
                ("07:00", "Controller or Namespace Structure (CNS): The structure."),
            ),
            "5.2",
            "Foo Identify command",
        ),
        placed(
            figure_of(
                5,
                "Command Dword 11 - CNS Specific Identifier",
                ("Bits", "Description"),
                ("15:00", "Set Identifier (SETID): The set."),
            ),
            "5.2.1",
            "Foo Set List (CNS 04h, CSI 02h)",
        ),
        placed(
            figure_of(
                6,
                "Command Dword 11 - CNS Specific Identifier",
                ("Bits", "Description"),
                ("15:00", "Group Identifier (GID): The group."),
            ),
            "5.2.2",
            "Foo Group List (19h)",
        ),
    )
    commands = spec.command_sets["admin"].commands
    operations = {
        name: [
            (o.name, o.selectors, [d.source.figure_nr for d in o.sqe])
            for o in commands[name].operations
        ]
        for name in ("foo_get", "foo_identify")
    }
    assert operations == {
        "foo_get": [("Foo Frequency", {"CID": 1}, [3])],
        "foo_identify": [
            ("Foo Set List", {"CNS": 4, "CSI": 2}, [5]),
            ("Foo Group List", {"CNS": 0x19}, [6]),
        ],
    }
    assert spec.unassigned == {}


def test_the_parts_of_a_value_split_over_two_fields_are_parts_of_it():
    """NUMDL and NUMDU of Get Log Page, "Number of Dwords Lower" and
    "Upper", in two dwords; "KV Key[63:00]" and "KV Key[127:64]" of KV 1.4"""

    from senfd.documents.spec import Part

    spec = document_of(
        figure_of(
            1,
            "Opcodes for Admin Commands",
            OPCODES,
            ("00b", "10b", "02h", "Foo Get", "5.1"),
        ),
        figure_of(
            2,
            "Foo Get - Command Dword 10",
            ("Bits", "Description"),
            ("31:16", "Number of Foos Lower (NUMFL): The lower bits."),
            ("15:00", "Foo Identifier (FID): The foo."),
        ),
        figure_of(
            3,
            "Foo Get - Command Dword 11",
            ("Bits", "Description"),
            ("31:16", "Reserved"),
            ("15:00", "Number of Foos Upper (NUMFU): The upper bits."),
        ),
        figure_of(
            4,
            "Foo Data Structure",
            ("Bytes", "Description"),
            ("07:00", "Foo Key[63:00]: The key."),
            ("15:08", "Foo Key[127:64]: The key."),
        ),
    )
    fields = {
        f.acronym or f.name: f.part
        for d in spec.command_sets["admin"].commands["foo_get"].sqe
        for f in d.fields
    }
    assert fields["NUMFL"] == Part(name="Number of Foos", acronym="NUMF", shift=0)
    assert fields["NUMFU"] == Part(name="Number of Foos", acronym="NUMF", shift=16)
    assert fields["FID"] is None
    (key,) = spec.structures
    assert [f.part for f in key.fields] == [
        Part(name="Foo Key", shift=0),
        Part(name="Foo Key", shift=64),
    ]
