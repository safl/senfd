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
    text = text.strip().lower()
    if kind == "hex":
        return re.sub(r"^0x|h$", "", text).lstrip("0") or "0"
    return ":".join(part.lstrip("0") or "0" for part in text.split(":"))


def value_pattern(item: Dict) -> str:
    """A pattern of the question's value as an answer of the data model writes it"""

    if item["kind"] == "hex":
        return rf"\b0*{int(item['a'], 16):X}h\b"
    parts = [rf"0*{int(p)}" for p in item["a"].split(":")]
    return r"(?:\| |: |^\s*)" + ":".join(parts) + r"(?: \||\s)"


def grade_value(item: Dict, answer: str) -> str:
    if not answer or answer.strip().lower() == "unknown":
        return UNKNOWN
    return (
        RIGHT
        if normal(item["kind"], answer) == normal(item["kind"], item["a"])
        else WRONG
    )


def grade_text(item: Dict, text: str) -> str:
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
    for line in text.splitlines():
        if named.search(line) and pattern.search(line):
            return RIGHT
    return WRONG


def tally(verdicts: List[str]) -> Dict[str, int]:
    return {v: verdicts.count(v) for v in (RIGHT, WRONG, UNKNOWN)}
