# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import pytest

from senfd.ranges import RangeError, parse


def test_a_span_is_its_bounds_and_its_width():
    rng = parse("bits", "31:16")
    assert (rng.kind, rng.upper, rng.lower, rng.width) == ("span", 31, 16, 16)
    assert (parse("bytes", "07").upper, parse("bytes", "07").lower) == (7, 7)


def test_a_formula_is_written_plainly_with_its_width_where_its_bounds_give_it():
    """As Base 2.4 writes the ranges of entries counted by a value it names"""

    rng = parse("bytes", "(n*32)-1:(n-1)*32")
    assert (rng.kind, rng.upper, rng.lower) == ("formula", None, None)
    assert (rng.formula, rng.width) == ("32*n - 1:32*n - 32", 32)
    assert parse("bytes", "(TLL-1):(TLL-K)").formula == "TLL - 1:TLL - K"
    assert parse("bytes", "TEL - 1: TEL - (EXATLEN + 4)").width is None
    assert parse("bytes", "BPSZ*128 KiB + 15:16").formula == "131072*BPSZ + 15:16"
    assert parse("bytes", "(Dword Count * 4)+3:4").formula == "4*Dword Count + 3:4"
    assert parse("bytes", "Impl Spec: 06").formula == "Impl Spec:6"


def test_a_footnote_marker_after_a_bound_is_no_term_of_it():
    """As the "1" after "EL-VSIL-K" of Base 2.4, Figure 258, marking note 1"""

    assert parse("bytes", "EL-VSIL-1: EL-VSIL-K 1").formula == (
        "EL - VSIL - 1:EL - K - VSIL"
    )


@pytest.mark.parametrize("text", ["n/a", "Impl Spec", "Variable Sized", "NOTE 1"])
def test_a_range_the_figure_leaves_open_is_open(text):
    rng = parse("bytes", text)
    assert (rng.kind, rng.upper, rng.lower, rng.formula) == ("open", None, None, None)


@pytest.mark.parametrize(
    "text, code, said",
    [
        ("(NUMENT-1)*32+63): ((NUMENT-1)*32+32)", "range", "')' after a whole"),
        ("((N *8) + 59: N + 60", "range", "does not close"),
        ("HDGSTF=1", "range", "'=1' is not of a formula"),
        ("3:2:1", "range", "more than two bounds"),
        ("N+", "range", "ends where a value was expected"),
        (" ", "range", "no range"),
        ("4*(N+1)+3: 4 * (N+4)", "range-reversed", "below the lower"),
        ("X + 59: X + 60", "range-reversed", "below the lower"),
        ("15:31", "range-reversed", "below the lower"),
    ],
)
def test_text_that_is_no_range_raises_saying_why(text, code, said):
    with pytest.raises(RangeError) as raised:
        parse("bytes", text)
    assert raised.value.code == code
    assert said in str(raised.value)


def test_bits_beyond_those_holding_them_are_no_range():
    with pytest.raises(RangeError) as raised:
        parse("bits", "64:00", holds=64)
    assert (raised.value.code, str(raised.value)) == (
        "range-outside",
        "bit 64 beyond the 64 bits",
    )
    assert parse("bits", "63:00", holds=64).width == 64
    assert parse("bytes", "64:00", holds=64).width == 65
