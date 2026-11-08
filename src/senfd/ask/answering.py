# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
A question answered: read or chosen, looked up, grounded, and its answer
said, with where the fields asked of are
"""

import re
import time
from typing import List, Optional, Tuple

from senfd.ask import language_model
from senfd.ask.grounding import SEVERAL, ambiguous, elsewhere, nothing, unmentioned
from senfd.ask.lookup import answer
from senfd.ask.phrasing import FILLER, terms, words_of
from senfd.ask.reading import spot, understand
from senfd.ask.vocabulary import Vocabulary
from senfd.documents.spec import SpecDocument


def respond(
    spec: SpecDocument,
    question: str,
    vocabulary: Vocabulary,
    llm: Optional[str] = None,
    tries: int = 3,
) -> Tuple[str, List[str]]:
    """The answer to 'question', and what it was understood as, each try"""

    if llm is None:
        understood = understand(question, vocabulary)
        if understood.query == "help":
            return "\n".join(answer(spec, understood)), [str(understood)]
        attempts = [(understood, answer(spec, understood, vocabulary))]
    else:
        attempts = []
        messages = [
            {"role": "system", "content": language_model.SYSTEM},
            {"role": "user", "content": question},
        ]
        for _ in range(tries):
            understood = language_model.choose(llm, messages)
            if understood.query == "unknown":
                attempts.append((understood, []))
                break
            lines = answer(spec, understood, vocabulary)
            attempts.append((understood, lines))
            missing = unmentioned(question, lines)
            other = elsewhere(question, understood, lines, vocabulary)
            if not (nothing(lines) or ambiguous(lines) or missing or other):
                break
            if nothing(lines) or ambiguous(lines):
                feedback = lines[0] if lines else "Nothing was found"
            elif other == SEVERAL:
                feedback = "The question names several commands, not one"
            elif other:
                feedback = f"The question is about {other}, the answer is not"
            else:
                feedback = f"The answer does not mention {', '.join(missing)}"
            messages.append({"role": "assistant", "content": understood.json()})
            messages.append({"role": "user", "content": feedback + "; choose another."})

    understood, lines = attempts[-1]
    tried = [str(u) for u, _ in attempts]
    missing = unmentioned(question, lines) if lines else []
    other = elsewhere(question, understood, lines, vocabulary) if lines else None
    # A language model's choice is grounded by what the question names
    ungrounded = (
        llm is not None and not terms(question) and not spot(question, vocabulary)
    )
    if llm is not None and ambiguous(lines):
        lines = []
    if (
        nothing(lines)
        or missing
        or other
        or ungrounded
        or understood.query == "unknown"
    ):
        if other == SEVERAL:
            why = "; the question names several commands rather than one"
        elif other and not nothing(lines):
            why = f"; what was found is not about {other}"
        elif missing and not nothing(lines):
            why = f"; what was found does not mention {', '.join(missing)}"
        else:
            why = ""
        return (
            f"_Understood as `{understood}`_\n\n"
            f"Not in the data model{why}, so this is not known. "
            "`help` says what can be asked."
        ), tried
    return f"_Understood as `{understood}`_\n\n" + "\n".join(lines), tried


def exchange(
    spec: SpecDocument,
    question: str,
    vocabulary: Vocabulary,
    llm: Optional[str] = None,
) -> Tuple[str, str]:
    """The answer to 'question', and a line saying how it was found: what it
    was read as, by how many lookups, in how long, citing how many figures"""

    began = time.perf_counter()
    try:
        text, tried = respond(spec, question, vocabulary, llm)
    except (OSError, ValueError, KeyError, IndexError) as exc:
        if llm is None:
            raise
        return f"The language model at {llm} did not choose a lookup: {exc}", ""
    took = (time.perf_counter() - began) * 1000
    figures = len(set(re.findall(r"\[[^\]]*Figure \d+[^\]]*\]", text)))
    lookups = f"{len(tried)} lookup" + ("s" if len(tried) != 1 else "")
    chosen = ", chosen by the language model" if llm else ""
    found = f"cites {figures} figure" + ("s" if figures != 1 else "")
    if "this is not known" in text:
        found = "not known"
    status = (
        f"read as {tried[-1] if tried else 'nothing'} | {lookups}{chosen} | "
        f"{took:.1f} ms | {found}"
    )
    return focused(question, text), status


def reply(
    spec: SpecDocument,
    question: str,
    vocabulary: Vocabulary,
    llm: Optional[str] = None,
) -> str:
    return exchange(spec, question, vocabulary, llm)[0]


# A heading citing its figure: "### Write: NVM command, opcode 01h [...]" of
# a command, feature or log page, "**cdw12 [...]**" of the table below it
CITED = re.compile(r"^(?:###|\*\*)\s*(.*?)\s*(\[[^\]]*\])\**\s*$")


def cells(line: str) -> Optional[List[str]]:
    """The cells of a row of a Markdown table, or None of another line"""

    if not line.startswith("|"):
        return None
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def focused(question: str, markdown: str, most: int = 3) -> str:
    """'markdown' with the rows of the fields 'question' asks of, by acronym
    or by name, in bold, and ending by saying where each is, citing its
    figure, as "> **FUA**, Force Unit Access, is bit 30 of cdw12 of Write
    [NVM 1.3, 3.3.6, Figure 71, page 54]"; of at most 'most' fields"""

    words = re.findall(r"[A-Za-z][A-Za-z0-9.]*", question)
    acronyms = {w.upper() for w in words} - {
        w.upper() for w in FILLER.findall(question)
    }
    spoken = words_of(question)
    title, label, cite, unit = "", "", "", "bits"
    lines, said = [], []
    for line in markdown.split("\n"):
        heading = CITED.match(line)
        if heading and line.startswith("###"):  # Of a command, feature, log page
            title, label = heading[1].split(":")[0], ""
        elif heading:  # Of the table below: a dword, a structure, a register
            label = re.sub(r",\s*(bits|bytes)$", "", heading[1])
            cite = heading[2]
        row = cells(line)
        if row and row[0] in ("Bits", "Bytes"):
            unit = row[0].lower()
        elif row and len(row) == 3 and row[0][:1].isdigit():
            at, name, acronym = row
            named = " " in name and words_of(name) in spoken
            if acronym.upper() in acronyms or named:
                line = "| " + " | ".join(f"**{c}**" if c else c for c in row) + " |"
                dword = title and label.startswith(("cdw", "cqe"))
                of = f"{label} of {title}" if dword else label or title
                field = f"**{acronym}**, {name}," if acronym else f"**{name}**"
                units = unit if ":" in at else unit[:-1]
                said.append(f"{field} is {units} {at} of {of} {cite}")
        lines.append(line)
    if not said:
        return markdown
    more = f" And {len(said) - most} more." if len(said) > most else ""
    return (
        "\n".join(lines) + "\n\n" + "\n>\n".join(f"> {s}" for s in said[:most]) + more
    )
