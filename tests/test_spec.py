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
