# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import re
from typing import List, Tuple


def pascal_to_snake(name):
    """Convert a PascalCase to snake_case"""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def snake_to_pascal(name):
    """Convert snake_case to PascalCase"""

    return "".join(word.capitalize() for word in name.split("_"))


# A footnote marker is printed as superscript digits; the readers of the
# documents give them as Unicode superscript digits, so that the data model can
# tell a marker from digits of the text, as "Controllers1" from "TSEN1"
SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
PLAIN = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")
MARK = "[⁰¹²³⁴⁵⁶⁷⁸⁹]+"
# Markers, one or more separated by commas, as "³, ⁴, ⁶"
REGEX_MARKS = re.compile(rf"\s*{MARK}(?:\s*,\s*{MARK})*")


def superscript(text: str) -> str:
    """'text' with its digits as superscript digits"""

    return text.translate(SUPERSCRIPT)


def unmarked(text: str, within: bool = False) -> Tuple[str, List[int]]:
    """
    'text' without the footnote markers at its end, and the numbers of those
    footnotes; with 'within', also without the markers after a word within
    it, as of "Entered by host request³ or by ITPT idle timer⁴". Superscript
    digits after a number other than 0 or 1, or after a lower-case letter
    standing alone, are an exponent, as of "2¹⁶" and "x⁶⁴", and are kept; after
    a lone 0 or 1 they are a marker, as of the bit size "0¹".
    """

    numbers: List[int] = []
    kept = []
    end = 0
    for match in REGEX_MARKS.finditer(text):
        before = text[: match.start()]
        last = text[match.end() :].strip() == ""
        # A marker may stand apart from its word, as "n/a ³"; an exponent not
        exponent = not match[0][0].isspace() and re.search(
            r"(?:(?<![0-9])[2-9]|[0-9]{2}|(?:^|[\s(+*-])[a-z])$", before
        )
        after_word = re.search(r"(?:[A-Za-z]|[.)])$", before)
        followed = re.match(r"[\s,.;:)/]|$", text[match.end() :])
        if exponent or not (last or (within and after_word and followed)):
            continue
        kept.append(text[end : match.start()])
        end = match.end()
        numbers += [int(n.translate(PLAIN)) for n in re.findall(MARK, match[0])]
    kept.append(text[end:])
    numbers = list(dict.fromkeys(numbers))
    return "".join(kept).rstrip() if numbers else text, numbers
