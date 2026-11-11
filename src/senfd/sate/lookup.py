# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
A question's reading looked up in the data model, as Markdown
"""

import re
from dataclasses import replace
from typing import Iterable, List

import senfd.query
from senfd.sate.phrasing import HELP, words_of
from senfd.sate.reading import Understood, spot
from senfd.sate.vocabulary import Vocabulary
from senfd.documents.spec import Bits, SpecDocument


def nothing(lines: List[str]) -> bool:
    """Whether 'lines' say that a lookup found nothing"""

    return not lines or lines[0].startswith(("No ", "Nothing named", "Give "))


def ambiguous(lines: List[str]) -> bool:
    """Whether 'lines' list what a name matches rather than answer, as
    "92 structures; be more specific" """

    return bool(lines) and bool(re.match(r"\d+ [a-z ]+; be more specific", lines[0]))


def resolved(
    spec: SpecDocument, understood: Understood, vocabulary: Vocabulary
) -> Understood:
    """'understood', or, of a command named with more than its name, as
    "Admin Track Send", the command its name names"""

    if understood.query != "command":
        return understood
    lines = senfd.query.command(spec, understood.argument, understood.dword)
    named = spot(understood.argument, vocabulary)
    if nothing(lines) and named and named[0] == "command":
        return replace(understood, argument=named[1])
    return understood


def holding(spec: SpecDocument, kind: str, words: str, most: int = 3) -> List[str]:
    """The identifiers of the features or log pages with a field named by all
    of 'words', as the Sanitize Status log page of "sanitize progress", where
    there are at most 'most'"""

    wanted = words_of(words).split()

    def named_by(fields: Iterable[Bits]) -> bool:
        return any(
            all(w in words_of(f"{f.name} {f.acronym or ''}").split() for w in wanted)
            or named_by(f.fields)
            for f in fields
        )

    found = []
    if kind == "log_page":
        for page in spec.log_pages.values():
            if page.structure and named_by(page.structure.fields):
                found.append(f"{page.identifier:02X}h")
    else:
        for feature in spec.features.values():
            if any(named_by(d.fields) for d in [*feature.sqe, *feature.cqe]):
                found.append(f"{feature.identifier:02X}h")
    return found if wanted and len(found) <= most else []


def answer(spec: SpecDocument, understood: Understood) -> List[str]:
    """The Markdown answering 'understood'; a feature or a log page not named
    by its argument, by the fields named by it; with the fields' descriptions
    where the question asked for them"""

    q = senfd.query
    describe = understood.describe
    if understood.query in ("feature", "log_page"):
        by = q.feature if understood.query == "feature" else q.log_page
        lines = by(spec, understood.argument, verbose=describe, markdown=True)
        if nothing(lines):
            keys = holding(spec, understood.query, understood.argument)
            held = [
                line
                for key in keys
                for line in by(spec, key, verbose=describe, markdown=True)
            ]
            return held or lines
        return lines
    found: List[str]
    if understood.query == "help":
        return [str(line) for line in HELP.splitlines()]
    if understood.query == "command":
        lines = q.command(
            spec, understood.argument, understood.dword, verbose=describe, markdown=True
        )
        if understood.opcode and lines and not nothing(lines):
            return lines[:1]  # The command's own line: its set, opcode and figure
        return lines
    if understood.query == "structure":
        return q.structure(spec, understood.argument, verbose=describe, markdown=True)
    if understood.query == "value":
        return bullets(
            q.value(spec, understood.argument, verbose=describe, markdown=True)
        )
    if understood.query == "status":
        return bullets(
            q.status(spec, understood.argument, verbose=describe, markdown=True)
        )
    if understood.query == "section":
        return bullets(q.section(spec, understood.argument))
    if understood.query == "errata":
        return bullets(q.errata(spec, understood.argument))
    if understood.query == "search":
        return bullets(q.search(spec, understood.argument, verbose=describe))
    if understood.query == "identifier":
        found = []
        for lines in (
            q.feature(spec, understood.argument, verbose=describe, markdown=True),
            q.log_page(spec, understood.argument, verbose=describe, markdown=True),
        ):
            if not nothing(lines):
                found += lines + [""]
        return found or [f"No feature or log page of identifier {understood.argument}"]
    if understood.query == "register":
        found = []
        for s in spec.structures:
            if s.name.lower().startswith(understood.argument.lower() + " - "):
                found += q.lines_of_structure(s, describe, markdown=True)
        return found or [f"No register {understood.argument}"]
    if understood.query == "acronym":
        return bullets(q.search(spec, understood.argument, verbose=describe))
    # A name: what has it, a command first, then a structure, else where it is
    for lines in (
        q.command(spec, understood.argument, verbose=describe, markdown=True),
        q.structure(spec, understood.argument, verbose=describe, markdown=True),
        q.feature(spec, understood.argument, verbose=describe, markdown=True),
        q.log_page(spec, understood.argument, verbose=describe, markdown=True),
    ):
        if not nothing(lines):
            return lines
    return bullets(q.search(spec, understood.argument, verbose=describe))


def bullets(lines: List[str]) -> List[str]:
    return lines if nothing(lines) else [f"- {line}" for line in lines]
