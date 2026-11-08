# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""What a question typed so far completes to, and which of its words are
recognised, for a session to offer and to colour as it is typed"""

import re
from typing import Dict, List, NamedTuple, Tuple

from senfd.ask.phrasing import GENERIC, KINDS_AFTER, QUESTION_WORDS, QUESTIONS, WORDS
from senfd.ask.reading import understand
from senfd.ask.vocabulary import Vocabulary


class Offer(NamedTuple):
    """A completion: 'text' replaces what was typed from 'start', counting
    back from its end; 'shown' is what the menu shows, of the kind 'kind'"""

    text: str
    start: int
    kind: str
    shown: str


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


def wanted(before: str) -> str:
    """The kind of name that comes after 'before', as a command after "opcode
    of ", or "" where none does"""

    return next((kind for words, kind in KINDS_AFTER if words.search(before)), "")


def fields_asked_of(before: str, vocabulary: Vocabulary) -> Dict[str, int]:
    """After "is", the acronyms of the fields of what 'before' asks of, as of
    cdw12 of Write in "which bit of cdw12 of Write is ", by their order"""

    if wanted(before) != "acronym":
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
    if wanted(typed) and typed.endswith(" "):
        found.append(("", typed))
    return [
        Tail(tail, wanted(before), fields_asked_of(before, vocabulary))
        for tail, before in found
    ]


def questions(typed: str) -> List[Offer]:
    """The common questions 'typed' begins, or with nothing typed, every one
    of them and the forms of questions, for someone who does not know them"""

    if not typed.strip():
        return [Offer(text, 0, "question", shown) for text, shown in QUESTIONS] + [
            Offer(word, 0, "form", word) for word in WORDS
        ]
    return [
        Offer(text, -len(typed), "question", shown)
        for text, shown in QUESTIONS
        if text.startswith(typed.lower()) and text != typed
    ]


def completions(vocabulary: Vocabulary, typed: str, most: int = 40) -> List[Offer]:
    """What completes 'typed', for a menu of at most 'most'.

    A question begun, as "which b", completes to the common questions it may
    be, shown with what goes in them, as "which bit of cdw<N> of <command> is
    <acronym>?". A name completes from where it starts in the question, so
    "opcode of zone app" completes to Zone Append, and a register also by its
    name, as "controller sta" to Controller Status. After the words of a
    kind, as "log page ", "opcode of " or "is ", names of that kind come
    first, offered before a letter of them is typed; after "is", the
    acronyms of the fields of what the question asks of come first, in the
    order of its figure. Then the most words matched come first, then the
    words of questions, commands, features, log pages, structures and
    acronyms, and the shorter name before the longer; a word typed in
    capitals, as "FU", is completed by acronyms before names."""

    begun = questions(typed)
    if not typed.strip():
        return begun
    kinds = [
        ("", WORDS),
        ("command", sorted(vocabulary.commands)),
        ("feature", sorted(vocabulary.features)),
        ("log page", sorted(vocabulary.log_pages)),
        ("structure", sorted(vocabulary.structures)),
        ("acronym", sorted(vocabulary.acronyms)),
    ]
    ends = tails(typed, vocabulary)
    best: Dict[str, Tuple[Tuple, Offer]] = {}
    for rank, (kind, names) in enumerate(kinds):
        for name in names:
            _, dash, rest = name.partition(" - ")
            for text in (name, rest) if dash and rest else (name,):
                tail = next(
                    (
                        t
                        for t in ends
                        if text.lower().startswith(t.typed.lower()) and text != t.typed
                    ),
                    None,
                )
                if tail is None:
                    continue
                capitals = len(tail.typed) > 1 and tail.typed.isupper()
                order = (
                    tail.fields.get(text, len(tail.fields))
                    if kind == "acronym"
                    else len(tail.fields)
                )
                key = (
                    order,  # The fields of what is asked of, by their figure
                    kind != tail.wanted,  # The kind the question wants
                    -tail.typed.count(" "),  # The most words matched
                    -1 if capitals and kind == "acronym" else rank,
                    len(text),
                    text,
                )
                if text not in best or key < best[text][0]:
                    best[text] = (key, Offer(text, -len(tail.typed), kind, text))
    ranked = [offer for _, offer in sorted(best.values())]
    return begun + ranked[: max(most - len(begun), 0)]


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
    for m in re.finditer(r"[A-Za-z][A-Za-z0-9.]*", text):
        if m[0] in vocabulary.acronyms and free(m.start(), m.end()):
            spans.append(Span(m.start(), m.end(), "acronym"))
    return sorted(spans)
