# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
A question read by its words, names and acronyms, as the query answering it
"""

import json
import re
from dataclasses import dataclass, replace
from typing import List, Optional, Tuple

from senfd.sate.phrasing import (
    ASKS_COMMAND,
    DWORD,
    GENERIC,
    singular,
    terms,
    words_of,
)
from senfd.sate.vocabulary import Vocabulary


@dataclass
class Understood:
    """A question as a query of the data model: its name and its arguments"""

    query: str
    argument: str = ""
    dword: Optional[int] = None
    describe: bool = False
    """Whether the answer gives the fields' descriptions too"""
    opcode: bool = False
    """Whether only the command's opcode is asked, as "opcode of write", and
    not its dwords"""

    def __str__(self) -> str:
        dword = f", dword={self.dword}" if self.dword is not None else ""
        describe = ", describe=True" if self.describe else ""
        opcode = ", opcode=True" if self.opcode else ""
        return f"{self.query}({self.argument!r}{dword}{describe}{opcode})"

    def json(self) -> str:
        return json.dumps(
            {"query": self.query, "argument": self.argument, "dword": self.dword}
        )


def spot(
    question: str, vocabulary: Vocabulary, only: Optional[str] = None
) -> Optional[Tuple[str, str]]:
    """The longest name of the data model the question names, with its kind, or of
    the kind 'only'; a register by its name, as "controller status" of
    "CSTS - Controller Status", and a structure by what its command
    qualifies, as "Identify Namespace" of "Identify - Identify Namespace" """

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
            register = bool(dash) and head.isupper()
            # A register is named by its name, a caption not by its qualifier;
            # a structure by what its command qualifies, "Identify Namespace"
            # of "Identify - Identify Namespace", where that is more than a word
            qualified = kind == "structure" and len(words_of(rest).split()) > 1
            forms = {name, rest} if register or (dash and qualified) else {name}
            for form in forms:
                key = words_of(form)
                if len(key.split()) == 1 and not set(key.split()) - GENERIC:
                    continue  # As "Command" of "CMD - Command", it names nothing
                if len(key) > 3 and key in asked:
                    argument = head if register else name
                    query = "register" if register else kind
                    found.append((len(key), -rank, query, argument))
    if not found:
        return None
    _, _, query, argument = max(found)
    return query, argument


# A question asking for the descriptions too, as "describe cdw12 of write"
DESCRIBE = re.compile(r"^(?:describe|explain)\b[\s:,-]*", re.I)


def described(text: str) -> Tuple[bool, str]:
    """Whether 'text' asks for the descriptions, by its first word, and the
    question after that word"""

    match = DESCRIBE.match(text)
    return (True, text[match.end() :]) if match else (False, text)


def understand(question: str, vocabulary: Vocabulary) -> Understood:
    """'question' as the query answering it: by its words where it is phrased
    as a query, as "feature 07h", else by the names and acronyms it names;
    led by "describe" or "explain", with the fields' descriptions"""

    describe, text = described(" ".join(question.strip().split()))
    understood = read_question(text, vocabulary)
    return replace(understood, describe=True) if describe else understood


def read_question(question: str, vocabulary: Vocabulary) -> Understood:
    """'question' as the query answering it, see understand()"""

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
    asked_status = status_asked(lower, command_named(text, vocabulary))
    if asked_status:
        return Understood("status", asked_status)
    code = hex_after(r"sc", lower)
    if code:  # A status code of any type, as "sc 81h"
        return Understood("value", f"status code {code}h")
    asks_command = re.search(ASKS_COMMAND, lower)
    # "status code 82h" and "which CNS value gives ..." ask of a table of values
    asked_value = value_asked(text, named) if not asks_command else ""
    if asked_value:
        return Understood("value", asked_value)
    # "opcode of write" asks the opcode alone; "cdw12 of write" a dword
    asks_opcode = bool(re.search(r"\b(?:opcodes?|opc)\b", lower))
    if asks_command:  # "opcode of identify controller" is the command
        command = command_named(text, vocabulary)
        named = ("command", command) if command else named
    # "feature 02h of Set Features" is that feature, whatever command carries it
    kind_and_id = re.search(
        r"\b(feature|fid|log ?page|lid|lpi)\s+(?:identifier\s+)?(?:0x)?([0-9a-f]{1,2})h?\b",
        lower,
    )
    if kind_and_id and not asks_command:
        kind = "feature" if kind_and_id[1] in ("feature", "fid") else "log_page"
        return Understood(kind, kind_and_id[2] + "h")
    identifier = re.search(r"\b(?:0x)?([0-9a-f]{1,2})h\b|\b0x([0-9a-f]{1,2})\b", lower)
    # An identifier in a question naming a command is a value of its fields
    if identifier and not (named and named[0] == "command"):
        key = (identifier[1] or identifier[2]) + "h"
        if re.search(r"\bfeature", lower):
            return Understood("feature", key)
        if re.search(r"\blog ?page|\blid\b|\blpi\b", lower):
            return Understood("log_page", key)
        return Understood("identifier", key)
    for prefix, query in (
        (r"(?:feature|feat)(?:\s+identifier)?\s+(?:of\s+)?", "feature"),
        (r"(?:log\s*page|lid|lpi)(?:\s+identifier)?\s+(?:of\s+)?", "log_page"),
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
    rest = " ".join(terms(text))
    # "Which log page reports sanitize progress?" asks of a log page, the
    # command's name only a word of what it holds; not "the log page
    # identifier of Get Log Page", which asks of the command carrying it
    asked_kind = kind_asked(lower)
    if (
        named
        and named[0] == "command"
        and asked_kind
        and not asks_command
        and not carries(named[1], asked_kind)
        and rest
    ):
        return Understood(asked_kind, rest)
    if named and named[0] == "command":
        return Understood(
            "command",
            named[1],
            int(dword[1]) if dword else None,
            opcode=asks_opcode and not dword,
        )
    if asks_command and not named and not registers and rest:
        argument = command_named(text, vocabulary) or rest
        return Understood(
            "command",
            argument,
            int(dword[1]) if dword else None,
            opcode=asks_opcode and not dword,
        )
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
    if not rest:  # Nothing that names anything, as "[" or "what is the"
        return Understood("help")
    return Understood("name", rest)


def hex_after(words: str, lower: str, most: int = 8) -> Optional[str]:
    """The hexadecimal value that follows 'words' in 'lower', as "81" of "sc
    0x81", "sc 81h" or "sc=81"; a value of letters alone must be written as
    hexadecimal, so "status bad" has none"""

    match = re.search(
        rf"\b(?:{words})\s*[=:]?\s*"
        rf"(?:0x([0-9a-f]{{1,{most}}})|([0-9a-f]{{1,{most}}})h|"
        rf"([0-9a-f]{{0,{most - 1}}}\d[0-9a-f]{{0,{most - 1}}}))\b",
        lower,
    )
    if not match:
        return None
    return (match[1] or match[2] or match[3]).upper()


def status_asked(lower: str, command: Optional[str]) -> str:
    """What a question asks of a status, as senfd.query.status() takes it:
    "4281h" of "what does status 0x4281 mean?", "dw3 85020000h" of "dword 3
    85020000h", or "sct 2h sc 81h" of "SCT 2 SC 81h", with " of Write" where
    it names a command; "" where it asks of none. "status code 82h" asks of a
    table of values, and "sc 81h" alone of a code of any type."""

    of = f" of {command}" if command else ""
    sct, sc = hex_after("sct", lower, 2), hex_after("sc", lower, 2)
    if sct and sc:
        return f"sct {sct}h sc {sc}h{of}"
    dword = hex_after(r"dw(?:ord)?\s?3", lower)
    if dword:
        return f"dw3 {dword}h{of}"
    held = hex_after(r"status(?:\s+field)?", lower, 4)
    return f"{held}h{of}" if held else ""


# A table of values as a question names its kind: a status code, a status
# code type, or a CNS value; "sct", "cns" and "status" alone with a value only,
# since alone they are a field's acronym or a word of a name
VALUE_KIND = re.compile(
    r"\b(?P<kind>status code types?|sct|status(?: codes?| values?)?|cns(?: values?)?)"
    r"(?:\s+(?:0x)?(?P<value>[0-9a-f]{1,2})h?\b)?"
)
HEX = r"\b(?:0x([0-9a-f]{1,2})|([0-9a-f]{1,2})h)\b"
KIND_WORDS = {"status", "code", "type", "sct", "cns", "value"}


def value_asked(text: str, named: Optional[Tuple[str, str]]) -> str:
    """What a question asks of a table of values, as senfd.query.value() takes
    it: "status code 82h" of "what is status code 82h?", or "status code zone
    boundary error" of a question naming the entry; "" where it asks of none,
    as "the CNS field of Identify" asks of the command's field; a command
    named is the command whose table it is, "the status codes of Ding" """

    lower = text.lower()
    match = VALUE_KIND.search(lower)
    if not match:
        return ""
    kind = re.sub(r"(code|type|value)s\b", r"\1", match["kind"])
    kind = {"sct": "status code type", "status value": "status code"}.get(kind, kind)
    kind = kind.replace("cns value", "cns")
    value = match["value"]
    if not value:
        anywhere = re.search(HEX, lower)
        value = (anywhere[1] or anywhere[2]) if anywhere else None
    if value:
        return f"{kind} {value}h"
    # "cns of identify controller" asks of the table, as "cns value of" does
    bare = match["kind"] in ("sct", "status") or (
        match["kind"] == "cns"
        and not re.match(r"\s+(?:of|for)\b", lower[match.end() :])
    )
    if bare or re.search(r"\bfields?\b", lower):
        return ""
    # A structure named is what a CNS value returns; a status code asked of a
    # log page or a structure named is a question of that, not of a table
    if named and named[0] != "command" and kind != "cns":
        return ""
    # Each word as written, since an entry is found by its words: "capabilities"
    rest = [
        w
        for w in re.findall(r"[a-z0-9/]+", lower)
        if len(w) > 1 and not {w, singular(w)} & (GENERIC | KIND_WORDS)
    ]
    return f"{kind} {' '.join(rest)}" if rest else kind


# The commands that carry a feature or a log page, rather than are one
CARRIERS = {
    "feature": {"set features", "get features"},
    "log_page": {"get log page"},
}


def carries(command: str, kind: str) -> bool:
    """Whether 'command' carries things of 'kind', as Set Features features"""

    return command.lower() in CARRIERS.get(kind, set())


def kind_asked(lower: str) -> str:
    """The kind of thing a question asks which of, as "which log page", or
    the identifier of, as "the log page identifier of Cross-Controller
    Reset", which is the log page's, not the command's of that name; ""
    where it asks which of none"""

    match = re.search(
        r"\b(?:which|what)\s+(log ?page|feature)s?\b"
        r"|\b(log ?page|feature)\s+identifiers?\s+(?:of|for)\b"
        r"|\b(lid|lpi|fid)\s+(?:of|for)\b",
        lower,
    )
    if not match:
        return ""
    asked = match[1] or match[2] or match[3]
    return "feature" if asked in ("feature", "fid") else "log_page"


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
