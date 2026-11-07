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

    assert "#define FOO_SPEC_FOOBAR_DING_OPCODE 0x01" in text
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
