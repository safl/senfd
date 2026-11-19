# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import pytest

from senfd.documents.spec import Bits
from senfd.layout import Word, words


def bits(upper: int, lower: int, acronym: str = "") -> Bits:
    """A field at bits 'upper' to 'lower', reserved where it has no acronym"""

    return Bits(
        name=acronym or "Reserved",
        acronym=acronym or None,
        unit="bits",
        range=f"{upper}:{lower}",
        role="field" if acronym else "reserved",
        kind="span",
        upper=upper,
        lower=lower,
        width=upper - lower + 1,
    )


def shape(units):
    return [
        (u.offset, u.size, u.count, [(f.acronym, f.upper, f.lower) for f in u.fields])
        for u in units
    ]


def test_bit_fields_lie_in_the_smallest_aligned_unit_that_holds_them():
    """MP, MXPS and NOPS of the Power State Descriptor of Base 2.4, and the bytes of no
    field between them"""

    units = words(
        [
            bits(63, 32, "ENLAT"),
            bits(31, 26),
            bits(25, 25, "NOPS"),
            bits(24, 24, "MXPS"),
            bits(23, 16),
            bits(15, 0, "MP"),
        ],
        8,
    )
    assert shape(units) == [
        (0, 2, 1, [("MP", 15, 0)]),
        (2, 1, 1, []),
        (3, 1, 1, [("MXPS", 0, 0), ("NOPS", 1, 1)]),
        (4, 4, 1, [("ENLAT", 31, 0)]),
    ]


def test_units_that_share_bytes_are_one_unit():
    """P at bit 16 and STATUS at bits 31:17 of CQE Dword 3 share byte 2"""

    units = words([bits(31, 17, "STATUS"), bits(16, 16, "P"), bits(15, 0, "CID")], 4)
    assert shape(units) == [
        (0, 2, 1, [("CID", 15, 0)]),
        (2, 2, 1, [("P", 0, 0), ("STATUS", 15, 1)]),
    ]


def test_a_unit_crossing_its_natural_boundary_grows_to_hold_it():
    units = words([bits(23, 8, "MID"), bits(7, 0, "LOW")], 4)
    assert shape(units) == [(0, 4, 1, [("LOW", 7, 0), ("MID", 23, 8)])]


def test_a_wide_field_whose_bits_lie_in_its_first_unit_is_an_array_of_that_unit():
    """Directives Supported of Base 2.4 Figure 705 is 32 bytes, its bits in the first 2"""

    units = words(
        [
            bits(255, 16),
            bits(15, 15, "VSDIRS"),
            bits(14, 3),
            bits(2, 2, "DPDIRS"),
            bits(1, 1, "SDIRS"),
            bits(0, 0, "IDIRS"),
        ],
        32,
    )
    assert units == [Word(offset=0, size=8, count=4, fields=units[0].fields)]
    assert [f.acronym for f in units[0].fields] == [
        "VSDIRS",
        "DPDIRS",
        "SDIRS",
        "IDIRS",
    ]


def test_a_field_wider_than_8_bytes_is_a_unit_of_its_bytes_or_an_error():
    units = words([bits(255, 128, "KEY"), bits(7, 0, "LEN")], 32)
    assert shape(units) == [
        (0, 1, 1, [("LEN", 7, 0)]),
        (1, 15, 1, []),
        (16, 16, 1, [("KEY", 127, 0)]),
    ]
    with pytest.raises(ValueError):
        words([bits(130, 4, "ODD")], 32)
