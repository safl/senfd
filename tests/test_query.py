# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

from pathlib import Path

import pytest

import senfd.query
import senfd.sate.cli
from senfd.documents.spec import Source, Structure


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


def test_a_value_is_found_in_the_tables_of_its_kind_by_value_or_by_name(spec):
    assert senfd.query.value(spec, "status code 82h") == [
        "82h Foo Lost, Command Specific status code of Foo Get "
        "[example, 4, Figure 70, page 70]"
    ]
    assert senfd.query.value(spec, "status code type 7h") == [
        "7h Vendor Specific, Status Code Type (SCT) [example, 4, Figure 47, page 47]"
    ]
    assert senfd.query.value(spec, "CNS 0x1c")[0].startswith(
        "1Ch Foo namespace data, CNS value of Identify ["
    )
    assert senfd.query.value(spec, "status code of foo lost")[0].startswith("82h ")
    assert senfd.query.value(spec, "cns foo namespace")[0].startswith("1Ch ")
    assert senfd.query.value(spec, "status code type")[0].startswith("0h Generic")
    assert senfd.query.value(spec, "status code 99h") == [
        "No table of values has 'status code 99h'"
    ]
    assert senfd.query.value(spec, "status code 82h", verbose=True)[0].endswith(
        "]: Foo is lost.; section: Foo Errors"
    )


def test_a_value_of_no_kind_is_found_in_every_table_holding_it(spec):
    tables = [line.split(", ", 1)[1] for line in senfd.query.value(spec, "C0h")]
    assert tables[0].startswith("Generic Command status code, Foobar Command Set [")
    assert [t.split(" [")[0] for t in tables[1:4]] == [
        "log page identifier of Get Log Page",
        "feature identifier of Foobar Command Set",
        "requirement of Foo Feature",
    ]
    assert any(
        line.startswith("C1h to C3h ") for line in senfd.query.value(spec, "C2h")
    )
    assert senfd.query.within("C1h to C3h", 0xC2) and not senfd.query.within("Yes", 1)
    assert senfd.query.value(spec, "")[0].startswith("Give the kind of table")


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


def test_sate_looks_up_by_the_name_of_the_lookup(spec_path, capsys):
    assert senfd.sate.cli.main(["--spec", str(spec_path), "command", "ding", "10"]) == 0
    assert "Foo Count (FCNT)" in capsys.readouterr().out


def test_a_lookup_of_several_words_needs_no_quotes(spec_path, capsys):
    argv = ["command", "foo", "directive", "send", "--spec", str(spec_path)]
    assert senfd.sate.cli.main(argv) == 0
    assert "Bar Reset Count (BRC)" in capsys.readouterr().out


def test_a_question_in_quotes_is_a_question_whatever_its_first_word(spec_path, capsys):
    argv = ["--spec", str(spec_path), "--raw", "command ding, what is FCNT?"]
    assert senfd.sate.cli.main(argv) == 0
    assert capsys.readouterr().out.startswith("_Understood as")


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


def test_structures_of_one_name_come_with_the_base_specification_s_first(spec):
    def structure(name: str, document: str) -> Structure:
        source = Source(document=document, figure_nr=1)
        return Structure(name=name, kind="data_structure", unit="bytes", source=source)

    revision = "Specification, Revision 1-3 Ratified 2026-07-31"
    shared = spec.model_copy(
        update={
            "structures": [
                structure(
                    "Identify Controller", f"NVM Express Computational {revision}"
                ),
                structure(
                    "I/O Command Set Specific Identify Controller",
                    f"NVM Express NVM {revision}",
                ),
                structure(
                    "Identify Controller",
                    f"NVM Express Subsystem Local Memory {revision}",
                ),
                structure(
                    "Identify - Identify Controller", f"NVM Express Base {revision}"
                ),
            ]
        }
    )
    lines = senfd.query.structure(shared, "identify controller")
    assert [line.split(" [")[0] for line in lines if " bytes [" in line] == [
        "Identify - Identify Controller, bytes",
        "Identify Controller, bytes",
        "Identify Controller, bytes",
        "I/O Command Set Specific Identify Controller, bytes",
    ]
    assert [
        line.split("[")[1].split(" ")[0] for line in lines if " bytes [" in line
    ] == [
        "Base",
        "Computational",
        "Subsystem",
        "NVM",
    ]


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
        ["value", "status code 82h"],
    ):
        assert senfd.sate.cli.main(["--spec", str(spec_path), *argv]) == 0
    out = capsys.readouterr().out
    assert "Foo Config" in out and "Foo Statistics" in out and "Ding cdw10" in out
    assert "82h Foo Lost" in out


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


def test_markdown_gives_the_bits_of_a_byte_a_column_of_their_own(spec):
    # A table of bytes with bits within one of them has a Bits column; the bits
    # stand in it with nothing under Bytes, and the bytes with nothing under Bits
    lines = senfd.query.structure(spec, "Foo Statistics", markdown=True)
    assert "| Bytes | Bits | Name | Acronym |" in lines
    assert "|  | 7:1 | Reserved |  |" in lines
    assert "|  | 0 | Foo On | FATTR.FON |" in lines
    byte = next(line for line in lines if "| FATTR |" in line)
    assert byte.split("|")[2].strip() == ""  # Nothing under Bits for the byte
    assert byte.split("|")[1].strip()  # Its range under Bytes


def test_a_cell_keeps_a_table_a_table():
    assert senfd.query.cell("a | b\n c") == "a \\| b c"


def test_the_command_line_gives_markdown(spec_path, capsys):
    argv = ["--spec", str(spec_path), "--markdown", "structure", "Bar"]
    assert senfd.sate.cli.main(argv) == 0
    assert "| Bytes | Name | Acronym |" in capsys.readouterr().out


def test_the_same_erratum_in_many_rows_is_said_once(spec):
    twice = spec.errata[0].model_copy()
    folded = spec.model_copy(update={"errata": [spec.errata[0], twice]})
    (line,) = senfd.query.errata(folded)
    assert line.endswith(" (in 2 rows)")


def test_the_lint_says_what_is_the_authors_and_what_is_senfds(spec):
    lines = senfd.query.lint(spec)
    headings = [line for line in lines if not line.startswith("  ")]
    assert [h.rsplit(" (", 1)[0] for h in headings] == [
        "The authors': candidate errata",
        "The authors': document errors",
        "senfd's, or the figure's: rows that name no field",
        "senfd's, or the figure's: figures of no shape senfd models",
        "Worked examples, not data",
        "senfd's, or the caption's: dwords no command claims",
    ]
    assert headings[0].endswith(f"({len(senfd.query.errata(spec))})")
    errors = lines[lines.index(headings[1]) + 1 : lines.index(headings[2])]
    assert "  example, the table after Figure 80, page 80: Table wrapped" in (
        "\n".join(errors)
    )
    assert any(line.startswith("  example, 4, Figure 65") for line in lines)
    assert all(not line.startswith("  ") for line in senfd.query.lint(spec, "nothing"))


def test_a_command_is_found_by_its_opcode(spec):
    assert senfd.query.command(spec, "01h")[0].startswith("Ding: Foobar command")
    assert senfd.query.command(spec, "Ding") == senfd.query.command(spec, "01h")


def test_without_a_data_model_the_lookup_says_how_to_make_one(capsys):
    argv = ["errata", "--spec", "/no/such/model.json"]
    assert senfd.query.run("senfd", argv, senfd.query.FINDINGS, "") == 1
    assert "senfd <documents>.docx --output" in capsys.readouterr().err


def test_sections_sort_by_number_with_an_annex_last():
    sections = ["A.1", "5.2.10", "5.2.9", None, "B", "5.10"]
    ordered = sorted(sections, key=senfd.query.section_order)
    assert ordered == [None, "5.2.9", "5.2.10", "5.10", "A.1", "B"]
