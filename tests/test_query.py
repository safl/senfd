# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

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
    assert (
        lines[0] == "Ding: Foobar command, opcode 01h [example, 1.1, Figure 1, page 1]"
    )
    assert lines[1] == "cdw10 [example, 1.2, Figure 2, page 2]"
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
    source.section, source.page_nr = "5.1.10", 195
    assert senfd.query.cite(source) == "Base 2.2, 5.1.10, Figure 12, page 195"
    source.section, source.page_nr = None, None
    source.document = (
        "NVM Express NVM Command Set Specification, Revision 1-1 2024-08-05 Ratified"
    )
    assert senfd.query.cite(source) == "NVM 1.1, Figure 12"


def test_the_command_line_prints_the_answer(spec_path, capsys):
    assert senfd.query.main(["--spec", str(spec_path), "command", "ding", "10"]) == 0
    assert "Foo Count (FCNT)" in capsys.readouterr().out


def test_a_command_has_its_operations_with_their_selectors(spec):
    lines = senfd.query.command(spec, "foo directive send")
    assert "operation Bar Reset, DTYPE=01h DOPER=01h [example, 4, Figure" in "\n".join(
        lines
    )
    assert "  15:00 Bar Reset Count (BRC)" in lines


def test_verbose_gives_the_descriptions_and_the_headings(spec):
    lines = senfd.query.command(spec, "ding", 10, verbose=True)
    assert "    How many." in lines
    lines = senfd.query.structure(spec, "Bar", verbose=True)
    assert "  [Bar Specific]" in lines
    assert any(line.startswith("  Note: NOTES:") for line in lines)


def test_a_structure_of_the_name_given_comes_before_those_containing_it(spec):
    lines = senfd.query.structure(spec, "foo statistics")
    assert lines[0].startswith("Foo Statistics, bytes")
    assert senfd.query.structure(spec, "nothing") == ["No structure 'nothing'"]
    assert senfd.query.structure(spec, " ") == ["Give the name of a structure"]


def test_a_register_says_its_offset(spec):
    (first, *_) = senfd.query.structure(spec, "FOOCAP")
    assert first.startswith("FOOCAP - Foo Capabilities at offset 10h, bits")


def test_many_structures_of_a_name_are_listed_rather_than_shown(spec):
    lines = senfd.query.structure(spec, "foo")
    assert lines[0].endswith("structures; be more specific:")


def test_a_search_finds_commands_features_log_pages_and_structures(spec):
    lines = senfd.query.search(spec, "foo")
    assert any(line.startswith("feature C0h Foo Config") for line in lines)
    assert any(line.startswith("log page C0h Foo Statistics") for line in lines)
    assert any(line.startswith("structure Foo Statistics") for line in lines)
    assert lines[-1].startswith("... and ")
    assert any(
        line.startswith("command Foo Get, opcode ")
        for line in senfd.query.search(spec, "foo get")
    )
    assert senfd.query.search(spec, "") == ["Give an acronym or a name to search for"]
    assert senfd.query.search(spec, "nothing") == ["Nothing named 'nothing'"]


def test_a_search_finds_the_fields_of_features_and_of_no_command(spec):
    assert any(
        line.startswith("feature Foo Config cdw11")
        for line in senfd.query.search(spec, "FLVL")
    )
    assert any(
        line.startswith("zap cdw10") for line in senfd.query.search(spec, "ZCNT")
    )


def test_nothing_of_an_identifier_or_dword_says_so(spec):
    assert senfd.query.feature(spec, "EEh") == ["No feature 'EEh'"]
    assert senfd.query.log_page(spec, "EEh") == ["No log page 'EEh'"]
    assert (
        senfd.query.command(spec, "ding", 13)[-1] == "No figure describes cdw13 of Ding"
    )
    assert senfd.query.command(spec, "") == ["Give the name of a command"]
    assert "  no figure laying it out is known" in senfd.query.log_page(spec, "C1h")


def test_every_question_of_the_command_line(spec_path, capsys):
    for argv in (
        ["feature", "C0h"],
        ["log-page", "C0h"],
        ["structure", "Bar"],
        ["search", "FCNT"],
        ["-v", "command", "ding"],
    ):
        assert senfd.query.main(["--spec", str(spec_path), *argv]) == 0
    out = capsys.readouterr().out
    assert "Foo Config" in out and "Foo Statistics" in out and "Ding cdw10" in out


def test_the_model_is_found_by_the_environment_or_in_the_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("SENFD_SPEC", str(tmp_path / "spec.json"))
    assert senfd.query.default_spec_path() == tmp_path / "spec.json"
    monkeypatch.delenv("SENFD_SPEC")
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert (
        senfd.query.default_spec_path()
        == tmp_path / "senfd" / "merged.spec.document.json"
    )


def test_a_section_lists_what_its_figures_describe(spec):
    lines = senfd.query.section(spec, "1.2")
    assert lines[0] == "example 1.2 Ding command"
    assert "Ding cdw10 [example, 1.2, Figure 2, page 2]" in lines
    assert senfd.query.section(spec, "ding")[0] == "example 1.2 Ding command"
    assert senfd.query.section(spec, "9") == ["No section '9'"]
    assert senfd.query.section(spec, "") == ["Give the number or title of a section"]


def test_the_errata_say_where_they_are(spec):
    lines = senfd.query.errata(spec)
    assert any(
        line.startswith("example, 1") and "bit 64 beyond the 64 bits" in line
        for line in lines
    )
    assert senfd.query.errata(spec, "nothing") == ["No errata"]


def test_the_alternatives_of_a_union_say_so(spec):
    lines = senfd.query.structure(spec, "Foo Address")
    assert "  17:02 Foo IPv6 Address (FIP6) [union 0, alternative 0]" in lines
    assert "  05:02 Foo IPv4 Address (FIP4) [union 0, alternative 1]" in lines


def test_verbose_gives_the_values_a_field_takes(spec):
    lines = senfd.query.command(spec, "foo migrate", 10, verbose=True)
    assert "      = 0h Foo Pause" in lines
    assert any(line.startswith("operation Foo Pause, SEL=00h") for line in lines)


def test_markdown_gives_the_fields_as_a_table_under_where_they_are(spec):
    lines = senfd.query.command(spec, "ding", 10, markdown=True)
    assert lines[0].startswith("### Ding: Foobar command, opcode 01h [example")
    assert "**cdw10 [example, 1.2, Figure 2, page 2]**" in lines
    at = lines.index("| Bits | Name | Acronym |")
    assert lines[at + 1 :] == [
        "|---|---|---|",
        "| 31:16 | Reserved |  |",
        "| 15:00 | Foo Count | FCNT |",
    ]


def test_markdown_names_a_field_within_another_by_both_and_its_values(spec):
    lines = senfd.query.structure(spec, "Foo Entry", markdown=True)
    assert "| Bytes | Name | Acronym |" in lines
    assert any(line.startswith("| ") and "| FEP." in line for line in lines)
    lines = senfd.query.command(spec, "foo migrate", 10, verbose=True, markdown=True)
    assert any("Values: 0h Foo Pause" in line for line in lines)


def test_a_cell_keeps_a_table_a_table():
    assert senfd.query.cell("a | b\n c") == "a \\| b c"


def test_the_command_line_gives_markdown(spec_path, capsys):
    argv = ["--spec", str(spec_path), "--markdown", "structure", "Bar"]
    assert senfd.query.main(argv) == 0
    assert "| Bytes | Name | Acronym |" in capsys.readouterr().out
