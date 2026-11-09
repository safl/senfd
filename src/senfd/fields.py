# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
What a field of a layout is, made from what its figure gives or not at all

A field is one with a name, and an acronym where it has one, or it is what
holds a place: reserved, obsolete, vendor specific or ignored, which are named
by what they are. A row giving none of these leaves a field without what it
needs: making one raises Unnamed.
"""

import re
from typing import Literal, NamedTuple, Optional, Tuple

from senfd.ranges import Unconstructible

Role = Literal["field", "reserved", "obsolete", "vendor_specific", "ignored"]

# What holds a place, by the words its row begins with, and the name it has
PLACES: Tuple[Tuple[re.Pattern, Role, str], ...] = (
    (re.compile(r"^reserved\b", re.IGNORECASE), "reserved", "Reserved"),
    (re.compile(r"^obsolete\b", re.IGNORECASE), "obsolete", "Obsolete"),
    (
        re.compile(r"^vendor[- ]specific\b", re.IGNORECASE),
        "vendor_specific",
        "Vendor Specific",
    ),
    (re.compile(r"^ignored\b", re.IGNORECASE), "ignored", "Ignored"),
)

# What may follow the word of a place in a name that holds one, as "Reserved
# by PCI-SIG"; a name going on otherwise is a field's, as "Vendor Specific
# Information Available"
QUALIFIED = re.compile(r"^(?:\s+(?:by|for)\b.*)?$", re.IGNORECASE)


# How a sentence about a field begins, where a name of one does not
SENTENCE = re.compile(r"^(?:if|these|there|shall|refer)\b", re.IGNORECASE)
ELISION = re.compile(r"^(?:\.\.\.|\u2026)$")


class Unnamed(Unconstructible):
    """A row of a layout giving no name for its field"""

    def __init__(self, description: str):
        said = " ".join(description.split())
        super().__init__(f"no name in '{said[:60]}'")


class Identity(NamedTuple):
    """What a field is: its 'role', "field" or what it holds a place as, its
    name, and its acronym where it has one"""

    role: Role
    name: str
    acronym: Optional[str] = None


def identity(
    name: Optional[str], acronym: Optional[str], description: str = ""
) -> Identity:
    """What the field of 'name', 'acronym' and 'description' is; raises
    Unnamed where a row gives neither a name nor a place held"""

    for form, role, called in PLACES:
        if name is None:
            if form.match(description):
                return Identity(role, called, acronym)
        elif (match := form.match(name)) and QUALIFIED.match(name[match.end() :]):
            return Identity(role, name, acronym)
    if name:
        return Identity("field", name, acronym)
    if is_phrase(description):
        return Identity("field", " ".join(description.split()), acronym)
    raise Unnamed(description)


def is_phrase(text: str) -> bool:
    """Whether 'text', all a row gives of its field, is that field's name, as
    "Most significant 16 bits of the LBST", rather than a sentence about it,
    as "These bytes have no equivalent", or text cut short, as an acronym's
    parenthesis left open"""

    return (
        bool(text)
        and "\n" not in text
        and not text.rstrip().endswith(".")
        and text.count("(") == text.count(")")
        and len(text.split()) <= 12
        and not SENTENCE.match(text)
        and not ELISION.match(text)
    )
