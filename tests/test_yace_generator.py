import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from senfd.yace_generator import SpecHeaders, main

SPEC = Path("example") / "output" / "merged.spec.document.json"


@pytest.fixture
def header(tmp_path):
    """The spec header of the Foobar commands of the example"""

    options = {"spec": str(SPEC), "prefix": "foo_spec", "commands": "foobar"}
    wrote = SpecHeaders(tmp_path, options).generate()
    (path,) = wrote.headers
    (source,) = wrote.sources
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
    (path,) = SpecHeaders(tmp_path, options).generate().headers
    text = path.read_text(encoding="utf-8")
    assert "struct spec_foobar_ring {" in text
    assert "struct spec_foobar_ding {" not in text


def test_the_header_is_written_without_yace_too(tmp_path, capsys):
    assert main([str(tmp_path), f"spec={SPEC}", "commands=foobar:ding"]) == 0
    assert (tmp_path / "senfd" / "spec.h").exists()
    assert main([]) == 1


def test_yace_takes_the_header_in_its_strict_subset(tmp_path):
    """The header is as yace takes a header written by hand: its masks linked
    to their fields, and no diagnostic"""

    pytest.importorskip("yace")
    if shutil.which("cc") is None and shutil.which("gcc") is None:
        pytest.skip("no C compiler")
    options = {"spec": str(SPEC), "prefix": "foo_spec", "commands": "foobar"}
    (path,) = SpecHeaders(tmp_path / "gen", options).generate().headers
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "yace",
            str(path),
            "--output",
            str(tmp_path),
            "--strict",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "foo_spec.status").read_text().endswith("0 diagnostics\n")


@pytest.fixture
def structures(tmp_path):
    """The spec header of the data structures of the example"""

    options = {"spec": str(SPEC), "prefix": "foo_spec", "commands": "none"}
    (path,) = SpecHeaders(tmp_path, options).generate().headers
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
    (path,) = SpecHeaders(tmp_path, options).generate().headers
    text = path.read_text(encoding="utf-8")
    assert "\tstruct spec_example_foo_entry foo_entry[]; ///< Foo Entry" in text


def test_of_a_union_the_first_alternative_is_the_member(structures):
    assert (
        "\tuint8_t fip6[16]; ///< Foo IPv6 Address; or, in the same bytes, Foo IPv4"
        " Address (FIP4), bytes 17:2" in structures
    )


def test_only_the_structures_asked_for_are_written(tmp_path):
    options = {"spec": str(SPEC), "commands": "none", "structures": "example:fb_format"}
    (path,) = SpecHeaders(tmp_path, options).generate().headers
    text = path.read_text(encoding="utf-8")
    assert "struct __attribute__((packed)) spec_example_fb_format {" in text
    assert "foo_statistics" not in text
    options["structures"] = "none"
    (path,) = SpecHeaders(tmp_path, options).generate().headers
    assert "struct __attribute__((packed))" not in path.read_text(encoding="utf-8")


def test_the_identifiers_and_status_codes_are_enums(structures):
    assert "enum foo_spec_feature_identifier {" in structures
    assert "\tFOO_SPEC_FEATURE_FOO_CONFIG = 0xc0, ///< Foo Config (example" in (
        structures
    )
    assert "enum foo_spec_log_page_identifier {" in structures
    assert "\tFOO_SPEC_LOG_PAGE_FOO_EVENTS = 0xc1," in structures
    # The status codes by the document and the type of status they are of
    assert "enum foo_spec_example_generic_command_status {" in structures
    assert "\tFOO_SPEC_EXAMPLE_GENERIC_COMMAND_STATUS_FOO_INVALID = 0xc0," in structures


def test_an_enum_names_a_constant_given_again_by_its_value():
    from senfd.yace_generator import enum_lines

    lines = enum_lines("e", "E", [("A", 1, "a"), ("A", 1, "a"), ("A", 2, "b")])
    assert lines[4:6] == ["\tA = 0x1, ///< a", "\tA_2H = 0x2, ///< b"]
    assert enum_lines("e", "E", []) == []
