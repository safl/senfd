# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
The units of storage that hold the bit fields of a layout, for a generator of code

The documents give bit fields by their bits, as MP at bits 15:00 and MXPS at bit 24
of the Power State Descriptor, and name no integer that holds them. A generator of C
needs those integers. words() gives them: each unit is an integer of 1, 2, 4 or 8
bytes at an offset that is a multiple of its size, and holds the fields that lie in
it. senfd makes no such decision in the data model, since the documents make none.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from senfd.documents.spec import Bits

SIZES = (1, 2, 4, 8)


@dataclass
class Word:
    """
    A unit of storage: 'count' integers of 'size' bytes at byte 'offset', or, where
    'size' is none of 1, 2, 4 and 8, 'size' bytes of a field that is no integer. The
    'fields' lie in the first integer, at bits counted from its bit 0. A unit of no
    fields is reserved.
    """

    offset: int
    size: int
    count: int = 1
    fields: List[Bits] = field(default_factory=list)


def natural(lowest: int, highest: int) -> Optional[Tuple[int, int]]:
    """The offset and the size of the smallest unit at a multiple of its size that
    holds the bytes 'lowest' to 'highest', or None where no unit of 8 bytes does"""

    for size in SIZES:
        if lowest // size == highest // size:
            return lowest - lowest % size, size
    return None


def placed(fields: List[Bits], offset: int) -> List[Bits]:
    """'fields' at bits counted from byte 'offset'"""

    moved = []
    for each in fields:
        copy = each.model_copy()
        copy.lower = (each.lower or 0) - offset * 8
        copy.upper = (each.upper or 0) - offset * 8
        copy.range = f"{copy.upper:02d}:{copy.lower:02d}"
        if copy.upper == copy.lower:
            copy.range = f"{copy.lower:02d}"
        moved.append(copy)
    return moved


def words(fields: List[Bits], size: int) -> List[Word]:
    """
    The units that hold 'fields', bit fields of a layout of 'size' bytes, in the order
    of their offsets, with the reserved bytes between them as units of no fields.

    Each field that is not reserved lies in the smallest unit at a multiple of its size
    that holds it. Units that share bytes are one unit, as large as needed to hold
    both. A field wider than 8 bytes that starts and ends at byte boundaries is a unit
    of its own bytes. Where every field that is not reserved lies in the first unit
    of 8, 4, 2 or 1 bytes that divides 'size', as the bits of Directives Supported in
    the first 2 of its 32 bytes, the layout is one unit: an array of that unit with
    the fields in element 0.

    Raises ValueError for a field of no known bits, and for a field wider than 8 bytes
    that does not start and end at byte boundaries.
    """

    named = [f for f in fields if f.role != "reserved"]
    for each in named:
        if each.kind != "span" or each.upper is None:
            raise ValueError(f"'{each.name}' has no known bits")
    highest = max(((f.upper or 0) // 8 for f in named), default=size)
    for element in sorted(SIZES, reverse=True):
        if size > element and size % element == 0 and highest < element:
            return [
                Word(
                    offset=0,
                    size=element,
                    count=size // element,
                    fields=placed(named, 0),
                )
            ]

    units: List[Word] = []
    for each in sorted(named, key=lambda f: f.lower or 0):
        lowest, highest = (each.lower or 0) // 8, (each.upper or 0) // 8
        found = natural(lowest, highest)
        if found is None:
            if (each.lower or 0) % 8 or ((each.upper or 0) + 1) % 8:
                raise ValueError(f"'{each.name}' is wider than 8 bytes, within bytes")
            found = (lowest, highest - lowest + 1)
        offset, length = found
        unit = Word(offset=offset, size=length, fields=[each])
        while units and units[-1].offset + units[-1].size > unit.offset:
            last = units.pop()
            start = min(last.offset, unit.offset)
            end = max(last.offset + last.size, unit.offset + unit.size) - 1
            merged = natural(start, end) or (start, end - start + 1)
            unit = Word(
                offset=merged[0], size=merged[1], fields=last.fields + unit.fields
            )
        units.append(unit)

    laid: List[Word] = []
    at = 0
    for unit in units:
        if unit.offset > at:
            laid.append(Word(offset=at, size=unit.offset - at))
        laid.append(
            Word(
                offset=unit.offset,
                size=unit.size,
                fields=placed(unit.fields, unit.offset),
            )
        )
        at = unit.offset + unit.size
    if size > at:
        laid.append(Word(offset=at, size=size - at))
    return laid
