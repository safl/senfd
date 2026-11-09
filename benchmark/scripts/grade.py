# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
Grading of the answers to questions.json, shared by the lanes and the report

A closed-book answer is a value, as "3Dh" or "29:26", and is right when it is
the question's, written either way the specification writes it. An answer of
the data model, a table or a search's lines, is right when one of its lines is
about what the question is about, its 'about', and gives the question's value
there. Either is "unknown" when it says it does not know.
"""

import re
from typing import Dict, List

RIGHT, WRONG, UNKNOWN = "right", "wrong", "unknown"


def normal(kind: str, text: str) -> str:
    """A value as written, made comparable: hex without its prefix or suffix
    and leading zeroes, a bit range without leading zeroes and high bit
    first, a single bit as the range of itself, so "bit 30", "30:30" and
    "bytes 1804:1805" against "1805:1804" are one value each"""

    text = text.strip().lower()
    if kind == "hex":
        return re.sub(r"^0x|h$", "", text).lstrip("0") or "0"
    parts = [part.lstrip("0") or "0" for part in text.split(":")]
    if len(parts) == 1:
        parts = parts * 2
    if all(part.isdigit() for part in parts):
        parts.sort(key=int, reverse=True)
    return ":".join(parts)


def value_pattern(item: Dict) -> str:
    """A pattern of the question's value as an answer of the data model writes it"""

    if item["kind"] == "hex":
        return rf"\b0*{int(item['a'], 16):X}h\b"
    parts = [rf"0*{int(p)}" for p in item["a"].split(":")]
    return r"(?:\| |: |^\s*)" + ":".join(parts) + r"(?: \||\s)"


def values_in(kind: str, text: str) -> List[str]:
    """The values of 'kind' written in 'text', each once, normalised: the
    hex values as "1Fh" or "0x1F", the bit ranges as "60:59" or a bit "30" """

    if kind == "hex":
        found = re.findall(r"\b(?:0x[0-9a-f]+|[0-9a-f]+h)\b", text, re.IGNORECASE)
    else:
        found = re.findall(r"\b\d+(?::\d+)?\b", text)
    return list(dict.fromkeys(normal(kind, value) for value in found))


def grade_value(item: Dict, answer: str) -> str:
    """A closed-book answer: right when it gives the value and no other, as
    "1Fh" or "1Fh (Namespace Admin Label)"; unknown when it says so or gives
    no value; wrong otherwise"""

    if not answer or answer.strip().lower() == "unknown":
        return UNKNOWN
    if normal(item["kind"], answer) == normal(item["kind"], item["a"]):
        return RIGHT
    given = values_in(item["kind"], answer)
    if not given:
        return UNKNOWN
    return RIGHT if given == [normal(item["kind"], item["a"])] else WRONG


def subject_of(line: str, description: int = -1) -> str:
    """The part of a line of an answer that says what the line is about: a
    table row's cells but its description, the cell 'description' counts
    from its first, else the line before its citation and link"""

    bare = re.sub(r"\[[^\]]*\](?:\([^)]*\))?", "", line)
    if bare.lstrip().startswith("|"):
        cells = bare.split("|")[1:-1]
        if 0 <= description < len(cells):
            cells = cells[:description] + cells[description + 1 :]
        return "|".join(cells)
    return bare.split(":")[0] if ": " in bare else bare


def description_cell(text: str) -> int:
    """Which cell of the table rows of 'text' is the description, by the
    header row; -1 where none is"""

    for line in text.splitlines():
        if line.lstrip().startswith("|"):
            cells = [c.strip().lower() for c in line.split("|")[1:-1]]
            if "description" in cells:
                return cells.index("description")
            if cells and not all(set(c) <= set("-: ") for c in cells):
                return -1
    return -1


def grade_text(item: Dict, text: str) -> str:
    """An answer from the data model: right when a line about the asked
    field, the row marked in bold or not, gives the value"""

    if not text or "not known" in text or text.startswith("No "):
        return UNKNOWN
    about = item["about"]
    # An acronym is matched as a word, in capitals, as "ST" is not "Status"
    named = (
        re.compile(rf"\b{re.escape(about)}\b")
        if about.isupper()
        else re.compile(re.escape(about), re.IGNORECASE)
    )
    pattern = re.compile(value_pattern(item), re.IGNORECASE)
    description = description_cell(text)
    for line in text.replace("**", "").splitlines():
        if named.search(subject_of(line, description)) and pattern.search(line):
            return RIGHT
    return WRONG


def tally(verdicts: List[str]) -> Dict[str, int]:
    return {v: verdicts.count(v) for v in (RIGHT, WRONG, UNKNOWN)}
