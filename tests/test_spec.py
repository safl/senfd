# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import json
import runpy
from argparse import Namespace
from pathlib import Path

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

    codes = {
        d.message.split("'")[1]
        for d in spec.diagnostics
        if d.code == "dwords-unassigned"
    }
    assert "zap" in codes


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


def test_the_unions_of_a_layout_and_those_nested_in_it_have_numbers_of_their_own():
    from senfd.documents.spec import Bits, number_unions

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
