# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
A range of bits or bytes, made from the text of a figure or not at all

A figure gives a range by numbers, "31:16"; by a formula of values it names,
"(N*16)+15:N*16"; or leaves it open, "n/a", "Impl Spec". Of a formula, the
upper and the lower bound are sums of products of named values and
integers, the named values counts and sizes, none negative. Text of none of
these forms is no range, nor is a range whose upper bound is below its
lower, or beyond the bits that hold it: making one raises RangeError, which
says why.
"""

import re
from typing import Dict, Iterator, List, Optional, Tuple

from pydantic import BaseModel


class Unconstructible(ValueError):
    """What a figure gives that a value of the data model cannot be made
    from: 'code' says what kind of wrong, and the message why"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class RangeError(Unconstructible):
    """Text that is no range, with the code "range", "range-reversed" or
    'range-outside'"""


# A product of named values, by their names in order; () is the integer 1
Monomial = Tuple[str, ...]


class Expression:
    """A sum of products of named values and integers, as 'terms', the
    integer factor of each product by its names"""

    def __init__(self, terms: Dict[Monomial, int]):
        self.terms = {m: c for m, c in terms.items() if c}

    @classmethod
    def number(cls, value: int) -> "Expression":
        return cls({(): value})

    @classmethod
    def named(cls, name: str) -> "Expression":
        return cls({(name,): 1})

    def __add__(self, other: "Expression") -> "Expression":
        terms = dict(self.terms)
        for monomial, factor in other.terms.items():
            terms[monomial] = terms.get(monomial, 0) + factor
        return Expression(terms)

    def __neg__(self) -> "Expression":
        return Expression({m: -c for m, c in self.terms.items()})

    def __sub__(self, other: "Expression") -> "Expression":
        return self + -other

    def __mul__(self, other: "Expression") -> "Expression":
        terms: Dict[Monomial, int] = {}
        for a, x in self.terms.items():
            for b, y in other.terms.items():
                monomial = tuple(sorted(a + b))
                terms[monomial] = terms.get(monomial, 0) + x * y
        return Expression(terms)

    def constant(self) -> Optional[int]:
        """The integer it is, where it names no value"""

        if any(self.terms.keys() - {()}):
            return None
        return self.terms.get((), 0)

    def names(self) -> List[str]:
        return sorted({name for monomial in self.terms for name in monomial})

    def below_one(self) -> bool:
        """Whether it is below 1 whatever the values it names, none negative"""

        return all(c <= 0 for m, c in self.terms.items() if m) and (
            self.terms.get((), 0) < 1
        )

    def __str__(self) -> str:
        if not self.terms:
            return "0"
        said = ""
        # The named terms before the integer, those added before those taken
        ordered = sorted(
            self.terms.items(), key=lambda t: (not t[0], t[1] < 0, -len(t[0]), t[0])
        )
        for monomial, factor in ordered:
            factors = [str(abs(factor))] if abs(factor) != 1 or not monomial else []
            text = "*".join(factors + list(monomial))
            if not said:
                said = f"-{text}" if factor < 0 else text
            else:
                said += f" - {text}" if factor < 0 else f" + {text}"
        return said


# A token of a formula: a number, scaled by a unit as "128 KiB"; a name of
# words, as "NUMENT" or "Dword Count"; an elision of terms; or an operator
TOKEN = re.compile(
    r"\s*(?:(?P<number>\d+)(?:\s*(?P<scale>KiB|MiB)\b)?"
    r"|(?P<name>[A-Za-z][A-Za-z0-9_]*(?:[ \t]+[A-Za-z][A-Za-z0-9_]*)*)"
    r"|(?P<elision>\.\.\.|…)"
    r"|(?P<operator>[-+*()]))"
)
SCALE = {"KiB": 1024, "MiB": 1024 * 1024}

# The markers of footnotes after a bound ending in a name, as the "1" of
# "EL-VSIL-K 1"; a number cannot follow a whole value, so it is no term
FOOTNOTE = re.compile(r"(?<=[A-Za-z)])\s+\d+(?:\s*,\s*\d+)*\s*$")

# The texts of a range a figure leaves open, as said in lower case
OPEN = re.compile(
    r"^(?:n/a|not applicable(?: \(n/a\))?|impl spec|variable(?: sized)?|\.\.\.|"
    r"…|note\s*\d+)$"
)


def tokens(text: str) -> Iterator[Tuple[str, str]]:
    """The tokens of 'text', each its kind and its text"""

    at = 0
    text = text.rstrip()
    while at < len(text):
        match = TOKEN.match(text, at)
        if not match or match.end() == at:
            raise RangeError("range", f"'{text[at:].strip()}' is not of a formula")
        kind = next(k for k in ("number", "name", "elision", "operator") if match[k])
        if kind == "number" and match["scale"]:
            yield "number", str(int(match["number"]) * SCALE[match["scale"]])
        else:
            yield kind, match[kind]
        at = match.end()


def expression(text: str) -> Expression:
    """The formula of 'text': sums and differences of products of numbers,
    names and formulas in parentheses"""

    toks = list(tokens(text))
    if not toks:
        raise RangeError("range", "a bound is empty")
    at = 0

    def peek() -> Optional[str]:
        return toks[at][1] if at < len(toks) else None

    def factor() -> Expression:
        nonlocal at
        if at >= len(toks):
            raise RangeError("range", f"'{text}' ends where a value was expected")
        kind, value = toks[at]
        at += 1
        if kind == "number":
            return Expression.number(int(value))
        if kind in ("name", "elision"):
            return Expression.named(value)
        if value == "(":
            inner = sum_()
            if peek() != ")":
                raise RangeError(
                    "range", f"'{text}' opens a parenthesis it does not close"
                )
            at += 1
            return inner
        raise RangeError("range", f"'{text}' has '{value}' where a value was expected")

    def product() -> Expression:
        nonlocal at
        result = factor()
        while peek() == "*":
            at += 1
            result = result * factor()
        return result

    def sum_() -> Expression:
        nonlocal at
        result = product()
        while peek() in ("+", "-"):
            sign = toks[at][1]
            at += 1
            result = result + product() if sign == "+" else result - product()
        return result

    result = sum_()
    if at < len(toks):
        raise RangeError("range", f"'{text}' has '{toks[at][1]}' after a whole value")
    return result


class Range(BaseModel):
    """
    The bits or bytes of a field: a "span" of 'upper' and 'lower', a
    "formula" of the values a figure names, or 'open' where the figure leaves
    it so, as "n/a"; 'text' as the figure writes it
    """

    unit: str
    text: str
    kind: str = "span"
    upper: Optional[int] = None
    lower: Optional[int] = None
    formula: Optional[str] = None
    """Of a formula, its bounds written plainly, "upper:lower", as
    '32*n - 1:32*n - 32'"""
    width: Optional[int] = None
    """How many bits or bytes it is, where its bounds give it"""


def parse(unit: str, text: str, holds: Optional[int] = None) -> Range:
    """
    The range of 'text' counting 'unit', "bits" or 'bytes'; where 'holds'
    bits hold it, it must lie within them. Raises RangeError where it is no
    range.
    """

    text = " ".join(text.split())
    if not text:
        raise RangeError("range", "there is no range")
    if OPEN.match(text.lower()):
        return Range(unit=unit, text=text, kind="open")

    bounds = [FOOTNOTE.sub("", bound) for bound in text.split(":")]
    if len(bounds) > 2:
        raise RangeError("range", f"'{text}' has more than two bounds")
    upper = expression(bounds[0])
    lower = expression(bounds[-1])
    width = upper - lower + Expression.number(1)
    if width.below_one():
        raise RangeError("range-reversed", "upper bound below the lower")

    high, low = upper.constant(), lower.constant()
    if high is not None and low is not None:
        if holds is not None and unit == "bits" and high >= holds:
            raise RangeError("range-outside", f"bit {high} beyond the {holds} bits")
        return Range(unit=unit, text=text, upper=high, lower=low, width=high - low + 1)

    return Range(
        unit=unit,
        text=text,
        kind="formula",
        formula=f"{upper}:{lower}",
        width=width.constant(),
    )
