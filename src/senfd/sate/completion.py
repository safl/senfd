# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""What a question typed so far completes to, and which of its words are
recognised, for a session to offer and to colour as it is typed"""

import re
from typing import Dict, List, NamedTuple, Optional, Tuple

from senfd.sate.phrasing import (
    GENERIC,
    KINDS_AFTER,
    QUESTION_WORDS,
    QUESTIONS,
    WORDS,
    acronyms_of,
)
from senfd.sate.reading import understand
from senfd.sate.vocabulary import Vocabulary


class Offer(NamedTuple):
    """A completion: 'text' replaces what was typed from 'start', counting
    back from its end; 'shown' is what the menu shows, of the kind 'kind';
    of a question, 'parts' are its words, each with the kind of name it is,
    "" for the words of the question, so a menu can mark what to swap"""

    text: str
    start: int
    kind: str
    shown: str
    parts: Tuple[Tuple[str, str], ...] = ()


# The names a question is shown with where the data model has them
PREFERRED = {
    "command": "Write",
    "structure": "Identify Controller",
    "feature": "Number of Queues",
    "log_page": "SMART / Health Information",
}


def examples(vocabulary: Vocabulary) -> Dict[str, str]:
    """The names the common questions are shown with, from the data model: a
    command, one of its dwords and the acronyms of two of its fields, Write,
    12, FUA and PRINFO where it has them, else the first command with fields
    in a dword from 10; a structure, a feature and a log page, each by its
    shortest name where the preferred one is missing; and a status
    and a status code where it has the figure of the Status Field"""

    found = {"code": "02h"}
    for kind, names in (
        ("structure", vocabulary.structures),
        ("feature", vocabulary.features),
        ("log_page", vocabulary.log_pages),
    ):
        if names:
            shortest = min(names, key=lambda n: (len(n), n))
            found[kind] = PREFERRED[kind] if PREFERRED[kind] in names else shortest
    dwords = sorted(
        ((name, n) != ("write", 12), name != "write", n, name)
        for name, n in vocabulary.fields
        if n is not None and n >= 10
    )
    for _, _, n, name in dwords:
        acronyms = vocabulary.fields[(name, n)]
        command = next(c for c in vocabulary.commands if c.lower() == name)
        found.update(command=command, dword=str(n))
        found["acronym"] = "FUA" if "FUA" in acronyms else acronyms[0]
        found["acronyms"] = "PRINFO" if "PRINFO" in acronyms else acronyms[0]
        break
    if any("status field" in s.lower() for s in vocabulary.structures):
        found.update(status="0x4281", sct="1", sc="80h")
    return found


def example(shown: str, names: Dict[str, str]) -> Optional[Tuple[Tuple[str, str], ...]]:
    """The parts of the question 'shown' with its names in braces filled from
    'names', each with its kind; None where 'names' lack one of them"""

    parts = []
    for at, piece in enumerate(re.split(r"\{(\w+)\}", shown)):
        if at % 2 == 0:
            if piece:
                parts.append((piece, ""))
        elif piece in names:
            kind = "acronym" if piece.startswith("acronym") else "name"
            parts.append((names[piece], kind))
        else:
            return None
    return tuple(parts)


class Span(NamedTuple):
    """Characters 'start' to 'end' of a question, recognised as of 'kind':
    a word of questions, a name or an acronym"""

    start: int
    end: int
    kind: str


class Tail(NamedTuple):
    """What a name may complete: the end of what was typed, from the start of
    a word, with the kind of name wanted there and, after "is", the acronyms
    of the fields of what the question asks of, by their order"""

    typed: str
    wanted: str
    fields: Dict[str, int]


# How a name offered ranks, the least first: by the order of the fields of
# what is asked of; the kind wanted; the most words matched; a one-letter
# acronym last; the kind; and the shorter name, then the name
Rank = Tuple[int, bool, int, bool, int, int, str]


def kind_after(before: str) -> str:
    """The kind of name the words ending 'before' say comes next, as a
    command after "opcode of ", or "" where they say none"""

    return next((kind for words, kind in KINDS_AFTER if words.search(before)), "")


def wanted(before: str, vocabulary: Vocabulary) -> str:
    """The kind of name that comes after 'before': an acronym after "is" only
    where the question asks of a thing with fields, as "which bit of cdw12
    of Write is ", not "what is " """

    kind = kind_after(before)
    if kind == "acronym" and not fields_asked_of(before, vocabulary):
        return ""
    return kind


def fields_asked_of(before: str, vocabulary: Vocabulary) -> Dict[str, int]:
    """After "is", the acronyms of the fields of what 'before' asks of, as of
    cdw12 of Write in "which bit of cdw12 of Write is ", by their order"""

    if kind_after(before) != "acronym":
        return {}
    understood = understand(before, vocabulary)
    known = vocabulary.fields_of(understood.argument, understood.dword)
    return {acronym: order for order, acronym in enumerate(known)}


def tails(typed: str, vocabulary: Vocabulary) -> List[Tail]:
    """What names may complete of 'typed', the longest first: from the start
    of each of its words, but not a generic word alone, as "of"; and, after
    the words of a kind, as "log page ", nothing yet"""

    found = []
    for start in range(len(typed)):
        tail = typed[start:]
        if start and typed[start - 1] != " " or not tail.strip():
            continue
        if tail.strip().lower() not in GENERIC:
            found.append((tail, typed[:start]))
    if typed.endswith(" ") and wanted(typed, vocabulary):
        found.append(("", typed))
    return [
        Tail(tail, wanted(before, vocabulary), fields_asked_of(before, vocabulary))
        for tail, before in found
    ]


def questions(typed: str, vocabulary: Vocabulary) -> List[Offer]:
    """The common questions 'typed' begins, or with nothing typed, every one
    of them and the forms of questions, for someone who does not know them;
    each shown as an example from the data model, and left out where the
    data model has nothing to show it with"""

    names = examples(vocabulary)
    shown = [
        (text, parts)
        for text, form in QUESTIONS
        for parts in [example(form, names)]
        if parts is not None
    ]
    if not typed.strip():
        return [
            Offer(text, 0, "question", "".join(p for p, _ in parts), parts)
            for text, parts in shown
        ] + [Offer(word, 0, "form", word) for word in WORDS]
    return [
        Offer(text, -len(typed), "question", "".join(p for p, _ in parts), parts)
        for text, parts in shown
        if text.startswith(typed.lower()) and text != typed
    ]


def completions(vocabulary: Vocabulary, typed: str, most: int = 40) -> List[Offer]:
    """What completes 'typed', for a menu of at most 'most'.

    A question begun, as "which b", completes to the common questions it may
    be, each shown as an example with names from the data model, as "which
    bit of cdw12 of Write is FUA?". A name completes from where it starts in the question, so
    "opcode of zone app" completes to Zone Append, and a register also by its
    name, as "controller sta" to Controller Status. After the words of a
    kind, as "log page ", "opcode of " or "is ", names of that kind come
    first, offered before a letter of them is typed, and names of other
    kinds not at all while a name of that kind matches what was typed. A
    name typed in full is listed first among the names that begin with it,
    which shows that sate knows the name. After "is",
    the acronyms of the fields of what the question asks of come first, in
    the order of its figure. Then the most words matched come first, then the
    words of questions, commands, features, log pages, structures and
    acronyms, a one-letter acronym last, and the shorter name before the
    longer; a word typed in capitals, as "FU", is completed by acronyms
    before names. While a common question is begun, only the questions it
    may be are offered."""

    begun = questions(typed, vocabulary)
    if begun:  # While a common question is begun, only the questions it may be
        return begun
    # A register by its whole name, "CSTS - Controller Status", whose head is
    # the register's acronym
    registers = {
        name
        for name in vocabulary.structures
        if name.partition(" - ")[0] in vocabulary.registers
    }
    kinds = [
        ("form", WORDS),
        ("command", sorted(vocabulary.commands)),
        ("feature", sorted(vocabulary.features)),
        ("log page", sorted(vocabulary.log_pages)),
        ("register", sorted(registers)),
        ("structure", sorted(vocabulary.structures)),
        ("acronym", sorted(vocabulary.acronyms)),
    ]
    known = {
        "command": vocabulary.commands,
        "feature": vocabulary.features,
        "log page": vocabulary.log_pages,
        "register": registers | {n.partition(" - ")[2] for n in registers},
        "structure": vocabulary.structures,
        "cns": vocabulary.cns,
    }

    def wanted_as(text: str, kind: str, wanted: str) -> bool:
        """Whether 'text' of 'kind' is a name of the kind 'wanted'; after "cns
        of", a structure that a CNS value returns"""

        return kind == wanted or (wanted == "cns" and text in vocabulary.cns)

    ends = tails(typed, vocabulary)
    best: Dict[str, Tuple[Rank, Offer]] = {}
    for rank, (kind, names) in enumerate(kinds):
        for name in names:
            _, dash, rest = name.partition(" - ")
            # A register is offered by its whole name, typed by either part
            texts = (name,) if kind == "register" else (name, rest) if rest else (name,)
            for text in texts:
                begins = [text] + ([rest] if kind == "register" and rest else [])
                tail = next(
                    (
                        t
                        for t in ends
                        if any(b.lower().startswith(t.typed.lower()) for b in begins)
                    ),
                    None,
                )
                # Elsewhere a register completes as a structure, by either part
                if tail is None or kind == "register" and tail.wanted != "register":
                    continue
                capitals = len(tail.typed) > 1 and tail.typed.isupper()
                order = (
                    tail.fields.get(text, len(tail.fields))
                    if kind == "acronym"
                    else len(tail.fields)
                )
                key: Rank = (
                    order,
                    not wanted_as(text, kind, tail.wanted),
                    -tail.typed.count(" "),
                    kind == "acronym" and len(text) < 2,
                    -1 if capitals and kind == "acronym" else rank,
                    len(text),
                    text,
                )
                if text not in best or key < best[text][0]:
                    best[text] = (key, Offer(text, -len(tail.typed), kind, text))
    ranked = [offer for _, offer in sorted(best.values())]
    # After the words of a kind, as "feature ", a name of another kind is no
    # answer while a name of that kind matches what was typed: "Timestamp"
    # the feature, not the figure of the event named so
    for tail in ends:
        if tail.wanted in known and any(
            name.lower().startswith(tail.typed.lower()) for name in known[tail.wanted]
        ):
            ranked = [
                o
                for o in ranked
                if wanted_as(o.text, o.kind, tail.wanted) or o.kind == "acronym"
            ]
            break
    return ranked[:most]


def recognised(vocabulary: Vocabulary, text: str) -> List[Span]:
    """The words of 'text' that are words of questions, names or acronyms of
    the data model, a longer name before a shorter one within it"""

    spans: List[Span] = [
        Span(m.start(), m.end(), "word") for m in QUESTION_WORDS.finditer(text)
    ]

    def free(start: int, end: int) -> bool:
        return all(end <= s.start or start >= s.end for s in spans)

    for m in vocabulary.names.finditer(text):
        if free(m.start(), m.end()):
            spans.append(Span(m.start(), m.end(), "name"))
    for start, end, word in acronyms_of(text):
        typed_as_is = word in vocabulary.acronyms
        # "fua" is FUA, while "set" is not SET, nor "of" OF
        lowered = len(word) > 2 and word.lower() not in GENERIC
        if typed_as_is or lowered and word.upper() in vocabulary.acronyms:
            if free(start, end):
                spans.append(Span(start, end, "acronym"))
    return sorted(spans)
