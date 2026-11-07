import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from senfd.yace_generator import SpecHeaders, main

SPEC = Path("example") / "output" / "merged.spec.document.json"


def example(paths):
    """Of the files written, that of the example document"""

    (path,) = [p for p in paths if p.stem.endswith("_example")]
    return path


@pytest.fixture
def header(tmp_path):
    """The spec header of the Foobar commands of the example"""

    options = {"spec": str(SPEC), "prefix": "foo_spec", "commands": "foobar"}
    wrote = SpecHeaders(tmp_path, options).generate()
    path, source = example(wrote.headers), example(wrote.sources)
    return path.read_text(encoding="utf-8"), source.read_text(encoding="utf-8")


def test_a_command_is_a_struct_of_its_dwords_with_its_masks(header):
    text, _ = header

    assert "enum foo_spec_foobar_opcode {" in text
    assert "\tFOO_SPEC_FOOBAR_DING_OPCODE = 0x1, ///< Ding (example" in text
    assert "struct foo_spec_foobar_ding {" in text
    # A pair of dwords with a field across them is one member of 64 bits
    assert (
        "\tuint64_t cdw2_3; ///< Command Dwords 2 and 3, see FOO_SPEC_FOOBAR_DING_CDW2_3_*"
        in text
    )
    assert (
        "\tuint32_t cdw10; ///< Command Dword 10, see FOO_SPEC_FOOBAR_DING_CDW10_*"
        in text
    )
    assert "#define FOO_SPEC_FOOBAR_DING_CDW10_FCNT 0xffff" in text
    assert "; bits 15:0 of 'cdw10' */" in text
    # A dword described for a condition only gets that description's masks
    assert "#define FOO_SPEC_FOOBAR_DING_CDW11_FM 0x1" in text
    assert "; bit 0 of 'cdw11' */" in text


def test_the_function_making_a_command_is_declared_and_defined(header):
    text, source = header

    assert "spec_foobar_ding_init(struct foo_spec_foobar_ding *cmd);" in text
    assert "\tcmd->cdw0 = FOO_SPEC_FOOBAR_DING_OPCODE;" in source


def test_only_the_commands_asked_for_are_written(tmp_path):
    options = {"spec": str(SPEC), "commands": "foobar:ring"}
    path = example(SpecHeaders(tmp_path, options).generate().headers)
    text = path.read_text(encoding="utf-8")
    assert "struct spec_foobar_ring {" in text
    assert "struct spec_foobar_ding {" not in text


def test_the_header_is_written_without_yace_too(tmp_path, capsys):
    assert main([str(tmp_path), f"spec={SPEC}", "commands=foobar:ding"]) == 0
    assert (tmp_path / "senfd" / "spec_example.h").exists()
    assert main([]) == 1


def test_yace_takes_the_header_in_its_strict_subset(tmp_path):
    """The header is as yace takes a header written by hand: its masks linked
    to their fields, and no diagnostic"""

    pytest.importorskip("yace")
    if shutil.which("cc") is None and shutil.which("gcc") is None:
        pytest.skip("no C compiler")
    options = {"spec": str(SPEC), "prefix": "foo_spec", "commands": "foobar"}
    paths = SpecHeaders(tmp_path / "gen", options).generate().headers
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "yace",
            *map(str, paths),
            "--output",
            str(tmp_path),
            "--strict",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert (
        (tmp_path / f"{paths[0].stem}.status").read_text().endswith("0 diagnostics\n")
    )


@pytest.fixture
def structures(tmp_path):
    """The spec header of the data structures of the example"""

    options = {"spec": str(SPEC), "prefix": "foo_spec", "commands": "none"}
    path = example(SpecHeaders(tmp_path, options).generate().headers)
    return path.read_text(encoding="utf-8")


def test_a_structure_is_a_packed_struct_of_its_fields_at_their_offsets(structures):
    assert "struct __attribute__((packed)) foo_spec_example_foo_statistics {" in (
        structures
    )
    assert "\tuint64_t fcnt; ///< Foo Count, bytes 7:0" in structures
    assert "\tuint8_t rsvd9[503]; ///< Reserved, bytes 511:9" in structures
    assert "#define FOO_SPEC_EXAMPLE_FOO_STATISTICS_FATTR_FON 0x1" in structures
    # What it is of is no part of its name, and a log page is named so
    assert "struct __attribute__((packed)) foo_spec_example_foo_namespace {" in (
        structures
    )
    assert "foo_spec_example_log_foo_statistics {" in structures
    assert "_OPCODE" not in structures


def test_fields_named_by_their_index_are_an_array_with_the_rows_left_out(
    structures,
):
    assert (
        "\tuint8_t foo_slot_descriptor[256]; ///< Foo Slot Descriptor, 8 of 32 bytes,"
        in structures
    )
    # A string is of bytes, whatever its size
    assert "\tuint8_t fver[8]; ///< Foo Version, bytes 263:256" in structures


def test_entries_as_many_as_the_data_says_follow_the_struct(structures):
    assert (
        " * Followed, from byte 16, by as many Foo Entry as the data says, each a"
        " 'struct foo_spec_example_foo_entry'" in structures
    )
    # The struct of the entries comes before what it follows
    assert structures.index("foo_spec_example_foo_entry {") < structures.index(
        "foo_spec_example_foo_list {"
    )
    assert "\tuint8_t rsvd4[12]; ///< Reserved, bytes 15:4\n};" in structures


def test_the_bytes_of_a_field_are_no_masks_of_its_bits(structures):
    assert "\tuint64_t fep; ///< Foo Entry Pair, bytes 15:8\n" in structures
    assert "FOO_SPEC_EXAMPLE_FOO_ENTRY_FEP_" not in structures


def test_entries_are_a_flexible_array_when_asked_for(tmp_path):
    options = {"spec": str(SPEC), "commands": "none", "flexible": "1"}
    path = example(SpecHeaders(tmp_path, options).generate().headers)
    text = path.read_text(encoding="utf-8")
    assert "\tstruct spec_example_foo_entry foo_entry[]; ///< Foo Entry" in text


def test_of_a_union_the_first_alternative_is_the_member(structures):
    assert (
        "\tuint8_t fip6[16]; ///< Foo IPv6 Address; or, in the same bytes, Foo IPv4"
        " Address (FIP4), bytes 17:2" in structures
    )


def test_only_the_structures_asked_for_are_written(tmp_path):
    options = {"spec": str(SPEC), "commands": "none", "structures": "example:fb_format"}
    path = example(SpecHeaders(tmp_path, options).generate().headers)
    text = path.read_text(encoding="utf-8")
    assert "struct __attribute__((packed)) spec_example_fb_format {" in text
    assert "foo_statistics" not in text
    options["structures"] = "none"
    path = example(SpecHeaders(tmp_path, options).generate().headers)
    assert "struct __attribute__((packed))" not in path.read_text(encoding="utf-8")


def test_the_identifiers_and_status_codes_are_enums(structures):
    assert "enum foo_spec_example_feature_identifier {" in structures
    assert "\tFOO_SPEC_EXAMPLE_FEATURE_FOO_CONFIG = 0xc0, ///< Foo Config (example" in (
        structures
    )
    assert "enum foo_spec_example_log_page_identifier {" in structures
    assert "\tFOO_SPEC_EXAMPLE_LOG_PAGE_FOO_EVENTS = 0xc1," in structures
    # The status codes by the document and the type of status they are of
    assert "enum foo_spec_example_generic_command_status {" in structures
    assert "\tFOO_SPEC_EXAMPLE_GENERIC_COMMAND_STATUS_FOO_INVALID = 0xc0," in structures


def test_an_enum_names_a_constant_given_again_by_its_value():
    from senfd.yace_generator import enum_lines

    lines = enum_lines("e", "E", [("A", 1, "a"), ("A", 1, "a"), ("A", 2, "b")])
    assert lines[4:6] == ["\tA = 0x1, ///< a", "\tA_2H = 0x2, ///< b"]
    assert enum_lines("e", "E", []) == []


def test_the_status_codes_of_a_type_for_each_scope_are_enums_of_their_own(
    structures,
):
    assert "enum foo_spec_example_generic_command_foo_commands_status {" in (structures)
    assert "_FOO_COMMANDS_STATUS_FOO_CLASH = 0xc0," in structures
    # A scope naming a command set is that of the document
    assert "_GENERIC_COMMAND_STATUS_FOO_INVALID = 0xc0," in structures
    # The types of status are no status codes
    assert "enum foo_spec_example_status_code_type {" in structures
    assert "\tFOO_SPEC_EXAMPLE_STATUS_CODE_TYPE_VENDOR_SPECIFIC = 0x7," in structures


def test_a_run_numbered_from_one_is_an_array_named_by_its_acronym(structures):
    assert "\tuint32_t fr[5]; ///< Foo Result, 5 of 4 bytes, bytes 23:4" in structures
    # A byte no field has is one reserved byte, with its offset
    assert "\tuint8_t rsvd1; ///< Reserved, byte 1\n" in structures


def test_an_index_is_read_with_its_thousands_separated():
    from senfd.documents.spec import Bits
    from senfd.yace_generator import base_of, index_of

    field = Bits(unit="bytes", range="1:0", name="Foo Identifier 65,535")
    assert (index_of(field), base_of(field)) == (65535, "Foo Identifier")


def test_each_document_has_a_header_and_a_source_of_its_own(tmp_path):
    options = {"spec": str(SPEC), "prefix": "foo_spec"}
    wrote = SpecHeaders(tmp_path, options).generate()
    assert sorted(p.name for p in wrote.headers) == [
        "foo_spec_example.h",
        "foo_spec_invalid.h",
    ]
    # Only a document with commands has functions to define
    assert [p.name for p in wrote.sources] == ["foo_spec_example.c"]
    text = wrote.headers[0].read_text(encoding="utf-8")
    assert "#ifndef FOO_SPEC_EXAMPLE_H" in text


def test_a_document_is_named_by_its_abbreviation():
    from senfd.yace_generator import document_key, set_key_of

    title = "NVM Express Key Value Command Set Specification, Revision 1-2"
    assert document_key(title) == "kv"
    assert document_key("NVM Express TCP Transport Specification, Revision 1-1") == (
        "tcp"
    )
    assert (set_key_of("zoned_namespace"), set_key_of("nvm")) == ("zns", "nvm")


def test_a_layout_of_no_named_kind_is_written_without_its_abbreviation(
    structures,
):
    assert "struct __attribute__((packed)) foo_spec_example_foo_request_pdu {" in (
        structures
    )
