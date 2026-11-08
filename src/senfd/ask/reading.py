# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
A question read by its words, names and acronyms, as the query answering it
"""

import json
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from senfd.ask.phrasing import ASKS_COMMAND, DWORD, GENERIC, terms, words_of
from senfd.ask.vocabulary import Vocabulary


@dataclass
class Understood:
    """A question as a query of the data model: its name and its arguments"""

    query: str
    argument: str = ""
    dword: Optional[int] = None

    def __str__(self) -> str:
        dword = f", dword={self.dword}" if self.dword is not None else ""
        return f"{self.query}({self.argument!r}{dword})"

    def json(self) -> str:
        return json.dumps(
            {"query": self.query, "argument": self.argument, "dword": self.dword}
        )


def spot(
    question: str, vocabulary: Vocabulary, only: Optional[str] = None
) -> Optional[Tuple[str, str]]:
    """The longest name of the data model the question names, with its kind, or of
    the kind 'only'; a register by its name, as "controller status" of
    "CSTS - Controller Status" """

    asked = words_of(question)
    found: List[Tuple[int, int, str, str]] = []
    kinds = [
        ("command", vocabulary.commands),
        ("feature", vocabulary.features),
        ("log_page", vocabulary.log_pages),
        ("structure", vocabulary.structures),
    ]
    for rank, (kind, names) in enumerate(kinds):
        if only and kind != only:
            continue
        for name in names:
            head, dash, rest = name.partition(" - ")
            # A register is named by its name, a caption not by its qualifier
            for form in {name, rest} if dash and head.isupper() else {name}:
                key = words_of(form)
                if len(key.split()) == 1 and not set(key.split()) - GENERIC:
                    continue  # As "Command" of "CMD - Command", it names nothing
                if len(key) > 3 and key in asked:
                    argument = head if dash and kind == "structure" else name
                    query = "register" if dash and head.isupper() else kind
                    found.append((len(key), -rank, query, argument))
    if not found:
        return None
    _, _, query, argument = max(found)
    return query, argument


def understand(question: str, vocabulary: Vocabulary) -> Understood:
    """'question' as the query answering it: by its words where it is phrased
    as a query, as "feature 07h", else by the names and acronyms it names"""

    text = " ".join(question.strip().split())
    lower = text.lower().rstrip("?").strip()
    if lower in ("", "help", "?"):
        return Understood("help")

    match = re.match(r"errata\s*(.*)$", lower)
    if match:
        return Understood("errata", match[1])
    named = spot(text, vocabulary)
    # "Write Zeroes in NVMe 2.0" names a revision, not section 2.0
    match = re.search(r"\b([A-Z]?\d+(?:\.\d+)+)\b", text)
    if match and not named:
        return Understood("section", match[1])
    match = re.match(r"section\s+(.+)$", lower)
    if match:
        return Understood("section", match[1])
    match = re.match(r"search\s+(.+)$", lower)
    if match:
        return Understood("search", match[1])
    asks_command = re.search(ASKS_COMMAND, lower)
    if asks_command:  # "opcode of identify controller" is the command
        command = command_named(text, vocabulary)
        named = ("command", command) if command else named
    identifier = re.search(r"\b(?:0x)?([0-9a-f]{1,2})h\b|\b0x([0-9a-f]{1,2})\b", lower)
    # An identifier in a question naming a command is a value of its fields
    if identifier and not (named and named[0] == "command"):
        key = (identifier[1] or identifier[2]) + "h"
        if re.search(r"\bfeature", lower):
            return Understood("feature", key)
        if re.search(r"\blog ?page|\blid\b", lower):
            return Understood("log_page", key)
        return Understood("identifier", key)
    for prefix, query in (
        (r"(?:feature|feat)(?:\s+identifier)?\s+(?:of\s+)?", "feature"),
        (r"(?:log\s*page|lid)(?:\s+identifier)?\s+(?:of\s+)?", "log_page"),
        (r"(?:structure|struct)\s+", "structure"),
    ):
        match = re.match(prefix + r"(.+)$", lower)
        if match:
            return Understood(query, match[1])

    dword = re.search(DWORD, lower)
    capitals = [
        w for w in re.findall(r"\b[A-Z][A-Z0-9]+\b", text) if w in vocabulary.acronyms
    ]
    registers = [w for w in capitals if w in vocabulary.registers]
    # A register named by its acronym, "CSTS", is what a question without a
    # dword asks of, whatever command's name its words also make, "Shutdown";
    # not when it names a structure, whose field "VS" is also a register's
    if registers and not dword and not field_of_other(named, lower):
        return Understood("register", registers[0])
    if named and named[0] == "command":
        return Understood("command", named[1], int(dword[1]) if dword else None)
    rest = " ".join(terms(text))
    if asks_command and not named and not registers and rest:
        argument = command_named(text, vocabulary) or rest
        return Understood("command", argument, int(dword[1]) if dword else None)
    if registers and not field_of_other(named, lower):
        return Understood("register", registers[0])
    if named:
        return Understood(named[0], named[1])
    # A feature or log page named by part of its name, as "a log page for
    # rotational media", is looked up by the rest of the question's terms
    for word, query in (
        (r"\blog ?pages?\b", "log_page"),
        (r"\bfeatures?\b", "feature"),
    ):
        if re.search(word, lower) and rest:
            return Understood(query, rest)
    if capitals:
        return Understood("acronym", capitals[0])
    return Understood("name", rest or lower)


def command_named(question: str, vocabulary: Vocabulary) -> Optional[str]:
    """The command 'question' names: by its name, the longest, or by terms
    that name it and no other command, as "format" names "Format NVM" """

    named = spot(question, vocabulary, only="command")
    if named:
        return named[1]
    words = command_words(question, vocabulary)
    among = [
        c for c in vocabulary.commands if words and all(w in words_of(c) for w in words)
    ]
    return among[0] if len(among) == 1 else None


def command_words(question: str, vocabulary: Vocabulary) -> List[str]:
    """The terms of 'question' that are words of a command's name"""

    return [
        words_of(t)
        for t in terms(question)
        if any(words_of(t) in words_of(c) for c in vocabulary.commands)
    ]


def names_other(named: Optional[Tuple[str, str]]) -> bool:
    """Whether the longest name a question names is of other than a command
    or a register, as "Identify Controller" is, though "Identify" is a
    command's"""

    return named is not None and named[0] in ("feature", "log_page", "structure")


def field_of_other(named: Optional[Tuple[str, str]], lower: str) -> bool:
    """Whether a question asks of a field of the structure, feature or log page
    it names, as "the VS field of the Identify Controller structure", whose
    acronym is a register's too, rather than of the register"""

    kind = r"\bfields?\b|\bstructures?\b|\bfeatures?\b|\blog ?pages?\b"
    return names_other(named) and bool(re.search(kind, lower))
