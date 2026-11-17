# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import re
from typing import List, Tuple


REGEX_IO = re.compile(r"\bI/O\b", re.IGNORECASE)


def key_of(text: str) -> str:
    """
    The key of a name or a header: lower case, words joined by underscores, and "I/O" as
    one word, for example "create_io_completion_queue" for "Create I/O Completion Queue"
    """

    return re.sub(r"[^a-z0-9]+", "_", REGEX_IO.sub("io", text).lower()).strip("_")


def pascal_to_snake(name):
    """Convert a PascalCase to snake_case"""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def snake_to_pascal(name):
    """Convert snake_case to PascalCase"""

    return "".join(word.capitalize() for word in name.split("_"))


# The readers of the documents return a footnote marker, which is printed as superscript
# digits, as Unicode superscript digits. senfd can then tell a marker from digits of the
# text, which it could not in "Controllers1" and "TSEN1".
SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
PLAIN = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")
MARK = "[⁰¹²³⁴⁵⁶⁷⁸⁹]+"
# One or more markers separated by commas, for example "³, ⁴, ⁶"
REGEX_MARKS = re.compile(rf"\s*{MARK}(?:\s*,\s*{MARK})*")


def superscript(text: str) -> str:
    """'text' with its digits replaced by superscript digits"""

    return text.translate(SUPERSCRIPT)


def unmarked(text: str, within: bool = False) -> Tuple[str, List[int]]:
    """
    'text' without the footnote markers at its end, and the numbers of those footnotes.
    With 'within', the markers after a word inside 'text' are removed too, for example
    in "Entered by host request³ or by ITPT idle timer⁴". Superscript digits after a
    number other than 0 or 1, or after a lowercase letter that stands alone, are an
    exponent and are kept, for example in "2¹⁶" and "x⁶⁴". Superscript digits after a
    lone 0 or 1 are a marker, for example in the bit size "0¹".
    """

    numbers: List[int] = []
    kept = []
    end = 0
    for match in REGEX_MARKS.finditer(text):
        before = text[: match.start()]
        last = text[match.end() :].strip() == ""
        # A marker can be separated from its word by a space, for example "n/a ³", and
        # an exponent cannot.
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
