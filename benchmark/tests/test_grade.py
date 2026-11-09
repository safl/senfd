# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import grade  # noqa: E402

HEX = {"kind": "hex", "a": "1F", "about": "Namespace Admin Label"}
BITS = {"kind": "bits", "a": "30", "about": "FUA"}


def test_a_value_dressed_up_is_still_the_value():
    assert grade.grade_value(HEX, "1Fh") == "right"
    assert grade.grade_value(HEX, "0x1f") == "right"
    assert grade.grade_value(HEX, "1Fh (Namespace Admin Label)") == "right"
    assert grade.grade_value(HEX, "82h or 83h") == "wrong"
    assert grade.grade_value(HEX, "1Eh") == "wrong"
    assert grade.grade_value(HEX, "I am not sure") == "unknown"
    assert grade.grade_value(HEX, "unknown") == "unknown"
    assert grade.grade_value(BITS, "bit 30") == "right"
    assert grade.grade_value(BITS, "30:30") == "right"
    bytes_ = {"kind": "bits", "a": "1805:1804", "about": "OFCS"}
    assert grade.grade_value(bytes_, "bytes 1804:1805") == "right"
    assert grade.grade_value(bytes_, "1805:1804") == "right"
    assert grade.grade_value(bytes_, "1803:1804") == "wrong"
    assert grade.grade_value(BITS, "bits 31:30") == "wrong"


def test_the_subject_of_a_line_is_its_cells_but_the_description_or_its_words_before_the_citation():
    row = "| 30 | Force Unit Access | FUA | A description of Write |"
    assert grade.subject_of(row, 3) == " 30 | Force Unit Access | FUA "
    assert (
        grade.subject_of(row)
        == " 30 | Force Unit Access | FUA | A description of Write "
    )
    assert (
        grade.subject_of(
            "Write: NVM command, opcode 01h [Base 2.4, Figure 1](https://x/y.pdf#page=2)"
        )
        == "Write"
    )
    assert (
        grade.subject_of("command Write, opcode 01h [NVM 1.3, Figure 20, page 30]")
        == "command Write, opcode 01h "
    )
    assert (
        grade.description_cell(
            "| Bits | Name | Acronym | Description |\n|---|---|---|---|\n| 30 | x | y | z |"
        )
        == 3
    )
    assert (
        grade.description_cell("| Bytes | Bits | Name | Acronym |\n|---|---|---|---|")
        == -1
    )


def test_a_line_about_something_else_holding_the_value_is_not_right():
    table = "| Bits | Name | Acronym | Description |\n|---|---|---|---|\n| 30 | Force Unit Access | FUA | ... |"
    assert grade.grade_text(BITS, table) == "right"
    other = "| Bits | Name | Acronym | Description |\n|---|---|---|---|\n| 30 | Limited Retry | LR | Set with FUA in the Write command |"
    assert grade.grade_text(BITS, other) == "wrong"
    assert (
        grade.grade_text(BITS, "Not in the data model, so this is not known.")
        == "unknown"
    )
