# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import pytest

from senfd.fields import Identity, Unnamed, identity


def test_a_field_is_its_name_and_acronym():
    assert identity("Force Unit Access", "FUA") == Identity(
        "field", "Force Unit Access", "FUA"
    )


@pytest.mark.parametrize(
    "description, role, name",
    [
        ("Reserved for future use.", "reserved", "Reserved"),
        ("Obsolete. Refer to Revision 1.0.", "obsolete", "Obsolete"),
        ("Vendor specific", "vendor_specific", "Vendor Specific"),
        ("Ignored by the controller", "ignored", "Ignored"),
    ],
)
def test_what_holds_a_place_is_named_by_what_it_is(description, role, name):
    assert identity(None, None, description) == Identity(role, name)


@pytest.mark.parametrize(
    "name, role",
    [
        ("Reserved", "reserved"),
        ("Reserved by PCI-SIG", "reserved"),
        ("Vendor Specific", "vendor_specific"),
        ("Obsolete", "obsolete"),
    ],
)
def test_a_place_given_a_name_keeps_it(name, role):
    assert identity(name, None) == Identity(role, name)


@pytest.mark.parametrize(
    "name, acronym",
    [
        ("Vendor Specific Information Available", "VSIA"),
        ("Vendor Specific Event Descriptor 0", None),
        ("Reserved Bandwidth", "RBW"),
    ],
)
def test_a_name_going_on_past_a_word_of_a_place_is_of_a_field(name, acronym):
    """As Base 2.4 names the Vendor Specific Information Available field of
    the Error Information Log Entry, which holds no place"""

    assert identity(name, acronym) == Identity("field", name, acronym)


def test_a_phrase_that_is_all_a_row_gives_is_its_name():
    text = "Most significant 16 bits of the LBST"
    assert identity(None, None, text) == Identity("field", text)


@pytest.mark.parametrize(
    "description",
    [
        "",
        "These bytes have no equivalent in this specification",
        "Shall be cleared to zero for NVM Express use",
        "Refer to the NVM Command Set Specification",
        "A sentence ending in a full stop.",
        "One line\nand another",
        "Bus Master Enable (BME",
        "...",
    ],
)
def test_a_row_giving_no_name_makes_no_field(description):
    with pytest.raises(Unnamed) as raised:
        identity(None, None, description)
    assert "no name" in str(raised.value)
