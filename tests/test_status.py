# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import pytest

import senfd.query
from senfd.documents.spec import Bits, Entry, Source, SpecDocument, Structure, Values


def field(acronym: str, name: str, upper: int, lower: int) -> Bits:
    written = f"{upper}:{lower}" if upper != lower else str(upper)
    return Bits(
        name=name,
        acronym=acronym,
        range=written,
        upper=upper,
        lower=lower,
        width=upper - lower + 1,
        unit="bits",
        role="field",
        kind="span",
    )


def table(qualifier, figure, entries, name=None) -> Values:
    return Values(
        kind="status_values",
        qualifier=qualifier,
        name=name,
        source=Source(document="Base", figure_nr=figure),
        entries=[Entry(value=v, name=n) for v, n in entries],
    )


@pytest.fixture(scope="module")
def spec() -> SpecDocument:
    """A data model of the figures a status is read by, with the bits of the
    Status Field as Dword 3 places them"""

    return SpecDocument(
        structures=[
            Structure(
                name="Completion Queue Entry: Status Field",
                kind="other",
                unit="bits",
                source=Source(document="Base", figure_nr=101),
                fields=[
                    field("DNR", "Do Not Retry", 31, 31),
                    field("M", "More", 30, 30),
                    field("CRD", "Command Retry Delay", 29, 28),
                    field("SCT", "Status Code Type", 27, 25),
                    field("SC", "Status Code", 24, 17),
                ],
            )
        ],
        values=[
            table(
                "Status Code Type",
                102,
                [
                    ("0h", "Generic Command Status"),
                    ("1h", "Command Specific Status"),
                    ("2h", "Media and Data Integrity Errors"),
                    ("7h", "Vendor Specific"),
                ],
            ),
            table("Generic Command", 103, [("02h", "Invalid Field in Command")]),
            table(
                "Command Specific",
                104,
                [("80h to BFh", "I/O Command Set Specific"), ("80h", "Conflicting")],
            ),
            table("Command Specific", 76, [("80h", "Of Write")], name="Write"),
            table(
                "Media and Data Integrity Error",
                107,
                [("81h", "Unrecovered Read Error")],
            ),
        ],
    )


def test_a_status_is_split_by_the_bits_of_the_status_field(spec):
    lines = senfd.query.status(spec, "4281h")

    assert lines[0].startswith(
        "Status 4281h of a completion: DNR 1 (Do Not Retry), M 0, CRD 0h, "
        "SCT 2h, SC 81h ["
    )
    assert lines[1].startswith("SCT 2h Media and Data Integrity Errors [")
    assert lines[2].startswith("SC 81h Unrecovered Read Error, Media and Data")


def test_dword_3_holds_the_status_above_the_phase_tag(spec):
    lines = senfd.query.status(spec, "dw3 80050007h")

    assert lines[0].startswith(
        "DW3 80050007h of a completion holds status 4002h: DNR 1 (Do Not Retry)"
    )
    assert lines[2].startswith("SC 02h Invalid Field in Command")


def test_a_type_and_a_code_are_looked_up_without_a_status(spec):
    lines = senfd.query.status(spec, "sct 0h sc 02h")

    assert lines[0].startswith("SCT 0h Generic Command Status [")
    assert lines[1].startswith("SC 02h Invalid Field in Command")
    assert len(lines) == 2


def test_a_code_of_its_own_is_given_rather_than_a_range_holding_it(spec):
    lines = senfd.query.status(spec, "sct 1h sc 80h")

    assert [line.split(",")[0] for line in lines[1:]] == [
        "SC 80h Of Write",
        "SC 80h Conflicting",
    ]


def test_a_command_named_keeps_the_codes_of_that_command(spec):
    lines = senfd.query.status(spec, "sct 1h sc 80h of write")

    assert [line.split(",")[0] for line in lines[1:]] == ["SC 80h Of Write"]


def test_a_command_with_no_codes_of_its_own_keeps_them_all(spec):
    lines = senfd.query.status(spec, "sct 1h sc 80h of read")

    assert len(lines[1:]) == 2


@pytest.mark.parametrize(
    "text, said",
    [
        ("sct 7h sc 01h", "SC 01h, which no table of Vendor Specific has"),
        ("sct 5h sc 01h", "SCT 5h, which no table of status code types has"),
        ("8000h", "Status 8000h has more bits than the Status Field"),
        ("what", "Give a status, as '4281h', or a type and a code"),
    ],
)
def test_what_the_tables_do_not_have_is_said(spec, text, said):
    assert senfd.query.status(spec, text)[-1].startswith(said)


def test_a_data_model_without_the_status_field_says_so():
    assert senfd.query.status(SpecDocument(), "4281h") == [
        "No figure of the Status Field in the data model"
    ]


@pytest.mark.parametrize(
    "question, first",
    [
        ("what does status 0x4281 mean?", "- Status 4281h of a completion"),
        ("what does dword 3 0x80050007 of a completion mean?", "- DW3 80050007h"),
        ("SCT 2 SC 81h", "- SCT 2h Media and Data Integrity Errors"),
        ("SC 0x81", "- **81h** Unrecovered Read Error"),
    ],
)
def test_a_status_question_is_answered_by_what_its_value_says(spec, question, first):
    from senfd.sate.answering import respond
    from senfd.sate.vocabulary import Vocabulary

    said, _ = respond(spec, question, Vocabulary.of(spec))

    answer = said.split("\n\n", 1)[1]
    assert not answer.startswith("Not in the data model")
    assert f"\n{first}" in f"\n{answer}"
