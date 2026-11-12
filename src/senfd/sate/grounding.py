# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
Whether an answer is about what its question asks of, and mentions what the
question names, so that an answer about something else is not shown
"""

import re
from typing import List, Optional, Tuple

from senfd.sate.phrasing import ASKS_COMMAND, DWORD, terms, words_of
from senfd.sate.reading import (
    Understood,
    carries,
    command_named,
    command_words,
    field_of_other,
    names_other,
    spot,
)
from senfd.sate.vocabulary import Vocabulary
from senfd.documents.spec import alias


SEVERAL = "several commands"


def heading(lines: List[str]) -> str:
    return next((line for line in lines if line.strip()), "")


def answered(lines: List[str]) -> Optional[Tuple[str, str]]:
    """The kind and name of what an answer by name is about, from its head"""

    first = heading(lines)
    for pattern, kind in (
        (r"^### (.+?): .*command", "command"),
        (r"^### Feature [0-9A-Fa-f]+h (.+?) \[", "feature"),
        (r"^### Log page [0-9A-Fa-f]+h (.+?) \[", "log_page"),
        (r"^\*\*(.+?)(?: at offset [^,]+)?, [a-z]+ \[", "structure"),
    ):
        match = re.match(pattern, first)
        if match:
            head, dash, _ = match[1].partition(" - ")
            if kind == "structure" and dash and head.isupper():
                return "register", match[1]
            return kind, match[1]
    return None


def elsewhere(
    question: str, understood: Understood, lines: List[str], vocabulary: Vocabulary
) -> Optional[str]:
    """What 'question' asks of that the answer 'lines' is not about, if any.

    The question asks of a kind of thing, by its words with the names it
    names taken out, "log page 02h" or "the opcode of Write", and the answer
    must be of that kind: a register named by its acronym is answered by
    that register, a command by that command and dword. And it names a
    thing, which a lookup by name finds and names at its head: that must be
    the thing named, not another whose name contains it, as "Memory Copy" of
    "Copy". Another lookup must mention what the question names."""

    if understood.query in ("value", "status"):
        # An entry found by every word of the question is about what it
        # names, and a status is what its value says
        return None
    found = answered(lines)
    kind, name = found if found else (None, None)
    named = spot(question, vocabulary)
    command = command_named(question, vocabulary)
    lower = question.lower()
    for taken in (named[1] if named else "", command or ""):
        if taken:
            lower = re.sub(rf"\b{re.escape(taken.lower())}\b", " ", lower)
    capitals = re.findall(r"\b[A-Z][A-Z0-9]+\b", question)
    registers = [c for c in capitals if c in vocabulary.registers]
    dword = re.search(DWORD, question.lower())

    if registers and not dword and not field_of_other(named, question.lower()):
        head = name.partition(" - ")[0] if name else None
        return None if kind == "register" and head in registers else registers[0]
    kinds = [
        of
        for word, of in (
            (r"\blog ?pages?\b|\blid\b", "log_page"),
            (r"\bfeatures?\b|\bfid\b", "feature"),
            (r"\bstructures?\b", "structure"),
        )
        # "the log page identifier in Get Log Page" asks of the command, and
        # "the Identify Controller data structure" not of Identify
        if re.search(word, lower) and not (command and not names_other(named))
    ]
    if kinds and kind not in kinds:
        return named[1] if named else f"a {kinds[0].replace('_', ' ')}"
    if not kinds and (re.search(ASKS_COMMAND, lower) or understood.query == "command"):
        if command is None:
            return (
                SEVERAL
                if command_words(question, vocabulary)
                else (None if understood.query == "command" else "a command")
            )
        if kind != "command" or alias(name or "") != alias(command):
            return command
        if dword and understood.dword is not None and understood.dword != int(dword[1]):
            return f"dword {dword[1]} of {command}"
        return None
    if not named:
        return None
    text = words_of(" ".join(lines))
    if named[0] == "command" and understood.query in ("feature", "log_page"):
        # A command carrying it, or lending a word to what it holds
        mentioned = words_of(named[1]) in text
        return None if carries(named[1], understood.query) or mentioned else named[1]
    if understood.query in ("feature", "log_page", "structure", "register"):
        if name is None:
            return named[1]
        head, _, rest = name.partition(" - ")
        names = {alias(name), alias(head), alias(rest)}
        return None if alias(named[1]) in names else named[1]
    return None if words_of(named[1]) in text else named[1]


def unmentioned(question: str, lines: List[str]) -> List[str]:
    """The terms of 'question' that the answer 'lines' does not mention"""

    text = " ".join(lines).lower()

    def pattern(term: str) -> str:
        # A value asked as "0x5" is the term 5h; the data model writes 05h
        if re.fullmatch(r"[0-9a-f]+h", term):
            return rf"(?<![a-z0-9])0*{term[:-1].lstrip('0') or '0'}h(?![a-z0-9])"
        return rf"(?<![a-z0-9]){re.escape(term)}s?(?![a-z0-9])"

    return [t for t in terms(question) if not re.search(pattern(t), text)]
