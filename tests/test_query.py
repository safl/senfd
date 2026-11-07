from pathlib import Path

import pytest

import senfd.query
from senfd.documents.spec import Source


@pytest.fixture(scope="module")
def spec_path():
    return Path("example") / "output" / "merged.spec.document.json"


@pytest.fixture(scope="module")
def spec(spec_path):
    return senfd.query.load(spec_path)


def test_a_command_is_its_opcode_and_dwords_with_where_they_are(spec):
    lines = senfd.query.command(spec, "ding", 10)
    assert lines[0].startswith("Ding: Foobar command, opcode 01h [example, Figure 1]")
    assert lines[1] == "cdw10 [example, Figure 2]"
    assert lines[2:] == ["  31:16 Reserved", "  15:00 Foo Count (FCNT)"]


def test_a_command_of_the_name_given_is_preferred_to_those_containing_it(spec):
    lines = senfd.query.command(spec, "ding")
    assert [line for line in lines if "command, opcode" in line] == [
        line for line in lines if line.startswith("Ding:")
    ]


def test_a_feature_and_a_log_page_are_found_by_identifier_or_name(spec):
    assert senfd.query.feature(spec, "C0h")[0].startswith("C0h Foo Config")
    assert senfd.query.feature(spec, "foo config")[0].startswith("C0h Foo Config")
    lines = senfd.query.log_page(spec, "0xC0")
    assert lines[0].startswith("C0h Foo Statistics")
    assert lines[1].startswith("Foo Statistics, bytes")


def test_a_search_finds_a_field_by_its_acronym(spec):
    lines = senfd.query.search(spec, "FCNT")
    assert any(line.startswith("Ding cdw10") for line in lines)


def test_nothing_found_says_so(spec):
    assert senfd.query.command(spec, "nothing") == ["No command 'nothing'"]


def test_a_source_is_cited_by_the_short_name_of_its_document():
    source = Source(
        document="NVM Express Base Specification, Revision 2-2 2025-03-11 Ratified",
        figure_nr=12,
    )
    assert senfd.query.cite(source) == "Base 2.2, Figure 12"
    source.document = (
        "NVM Express NVM Command Set Specification, Revision 1-1 2024-08-05 Ratified"
    )
    assert senfd.query.cite(source) == "NVM 1.1, Figure 12"


def test_the_command_line_prints_the_answer(spec_path, capsys):
    assert senfd.query.main(["--spec", str(spec_path), "command", "ding", "10"]) == 0
    assert "Foo Count (FCNT)" in capsys.readouterr().out
