# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
A question's reading looked up in the data model, as Markdown
"""

import re
from dataclasses import replace
from typing import List

import senfd.query
from senfd.ask.phrasing import HELP
from senfd.ask.reading import Understood, spot
from senfd.ask.vocabulary import Vocabulary
from senfd.documents.spec import SpecDocument


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


def answer(spec: SpecDocument, understood: Understood) -> List[str]:
    """The Markdown answering 'understood'"""

    q = senfd.query
    found: List[str]
    if understood.query == "help":
        return [str(line) for line in HELP.splitlines()]
    if understood.query == "command":
        return q.command(spec, understood.argument, understood.dword, markdown=True)
    if understood.query == "feature":
        return q.feature(spec, understood.argument, markdown=True)
    if understood.query == "log_page":
        return q.log_page(spec, understood.argument, markdown=True)
    if understood.query == "structure":
        return q.structure(spec, understood.argument, markdown=True)
    if understood.query == "section":
        return bullets(q.section(spec, understood.argument))
    if understood.query == "errata":
        return bullets(q.errata(spec, understood.argument))
    if understood.query == "search":
        return bullets(q.search(spec, understood.argument))
    if understood.query == "identifier":
        found = []
        for lines in (
            q.feature(spec, understood.argument, markdown=True),
            q.log_page(spec, understood.argument, markdown=True),
        ):
            if not nothing(lines):
                found += lines + [""]
        return found or [f"No feature or log page of identifier {understood.argument}"]
    if understood.query == "register":
        found = []
        for s in spec.structures:
            if s.name.lower().startswith(understood.argument.lower() + " - "):
                found += q.lines_of_structure(s, False, markdown=True)
        return found or [f"No register {understood.argument}"]
    if understood.query == "acronym":
        return bullets(q.search(spec, understood.argument))
    # A name: what has it, a command first, then a structure, else where it is
    for lines in (
        q.command(spec, understood.argument, markdown=True),
        q.structure(spec, understood.argument, markdown=True),
        q.feature(spec, understood.argument, markdown=True),
        q.log_page(spec, understood.argument, markdown=True),
    ):
        if not nothing(lines):
            return lines
    return bullets(q.search(spec, understood.argument))


def bullets(lines: List[str]) -> List[str]:
    return lines if nothing(lines) else [f"- {line}" for line in lines]
