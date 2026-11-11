# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""What a question typed so far completes to, and which of its words are
recognised, for a session to offer and to colour as it is typed"""

from typing import Dict, List, NamedTuple, Tuple

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

    begun = questions(typed)
    if begun:  # While a common question is begun, only the questions it may be
        return begun
    kinds = [
        ("form", WORDS),
        ("command", sorted(vocabulary.commands)),
        ("feature", sorted(vocabulary.features)),
        ("log page", sorted(vocabulary.log_pages)),
        ("structure", sorted(vocabulary.structures)),
        ("acronym", sorted(vocabulary.acronyms)),
    ]
    ends = tails(typed, vocabulary)
    best: Dict[str, Tuple[Rank, Offer]] = {}
    for rank, (kind, names) in enumerate(kinds):
        for name in names:
            _, dash, rest = name.partition(" - ")
            for text in (name, rest) if dash and rest else (name,):
                tail = next(
                    (t for t in ends if text.lower().startswith(t.typed.lower())),
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
                key: Rank = (
                    order,
                    kind != tail.wanted,
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
    known = {
        "command": vocabulary.commands,
        "feature": vocabulary.features,
        "log page": vocabulary.log_pages,
        "structure": vocabulary.structures,
    }
    for tail in ends:
        if tail.wanted in known and any(
            name.lower().startswith(tail.typed.lower()) for name in known[tail.wanted]
        ):
            ranked = [o for o in ranked if o.kind in (tail.wanted, "acronym")]
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
