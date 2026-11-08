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

from senfd.sate import language_model
from senfd.sate.grounding import SEVERAL, elsewhere, unmentioned
from senfd.sate.lookup import ambiguous, answer, nothing, resolved
from senfd.sate.phrasing import FILLER, acronyms_of, terms, words_of
from senfd.sate.reading import Understood, spot, understand
from senfd.sate.vocabulary import Vocabulary
from senfd.documents.spec import SpecDocument


# A lookup tried: what the question was read as, or chosen as, and its answer
Attempt = Tuple[Understood, List[str]]


def by_words(
    spec: SpecDocument, question: str, vocabulary: Vocabulary
) -> List[Attempt]:
    """The lookup 'question' is read as, by its words, names and acronyms"""

    understood = resolved(spec, understand(question, vocabulary), vocabulary)
    return [(understood, answer(spec, understood))]


def by_language_model(
    spec: SpecDocument, question: str, vocabulary: Vocabulary, llm: str, tries: int
) -> List[Attempt]:
    """The lookups a language model at 'llm' chooses for 'question': it is
    told what is wrong with an answer, and chooses again, 'tries' times at
    most"""

    attempts: List[Attempt] = []
    messages = [
        {"role": "system", "content": language_model.SYSTEM},
        {"role": "user", "content": question},
    ]
    for _ in range(tries):
        chosen = language_model.choose(llm, messages)
        if chosen.query == "unknown":
            attempts.append((chosen, []))
            break
        understood = resolved(spec, chosen, vocabulary)
        lines = answer(spec, understood)
        attempts.append((understood, lines))
        wrong = what_is_wrong(question, understood, lines, vocabulary)
        if not wrong:
            break
        messages.append({"role": "assistant", "content": understood.json()})
        messages.append({"role": "user", "content": wrong + "; choose another."})
    return attempts


def what_is_wrong(
    question: str, understood: Understood, lines: List[str], vocabulary: Vocabulary
) -> str:
    """What is wrong with 'lines' as the answer to 'question', said to a
    language model, or "" where nothing is"""

    if nothing(lines) or ambiguous(lines):
        return lines[0] if lines else "Nothing was found"
    other = elsewhere(question, understood, lines, vocabulary)
    if other == SEVERAL:
        return "The question names several commands, not one"
    if other:
        return f"The question is about {other}, the answer is not"
    missing = unmentioned(question, lines)
    if missing:
        return f"The answer does not mention {', '.join(missing)}"
    return ""


def respond(
    spec: SpecDocument,
    question: str,
    vocabulary: Vocabulary,
    llm: Optional[str] = None,
    tries: int = 3,
) -> Tuple[str, List[str]]:
    """The answer to 'question', and what it was understood as, each try. An
    answer about other than what the question asks of, or not mentioning
    what it names, is withheld as not known."""

    if llm is None:
        attempts = by_words(spec, question, vocabulary)
    else:
        attempts = by_language_model(spec, question, vocabulary, llm, tries)
    understood, lines = attempts[-1]
    tried = [str(u) for u, _ in attempts]
    if understood.query == "help":
        return "\n".join(lines), tried

    missing = unmentioned(question, lines) if lines else []
    other = elsewhere(question, understood, lines, vocabulary) if lines else None
    # A language model's choice is grounded by what the question names
    ungrounded = (
        llm is not None and not terms(question) and not spot(question, vocabulary)
    )
    if llm is not None and ambiguous(lines):
        lines = []
    said = f"_Understood as `{understood}`_\n\n"
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
        not_known = f"Not in the data model{why}, so this is not known. "
        return said + not_known + "`sate help` says what can be asked.", tried
    return said + "\n".join(lines), tried


def exchange(
    spec: SpecDocument,
    question: str,
    vocabulary: Vocabulary,
    llm: Optional[str] = None,
    said_as: bool = True,
) -> Tuple[str, str]:
    """The answer to 'question', and a line saying how it was found: what it
    was read as, by how many lookups, in how long, citing how many figures.
    Without 'said_as', the answer does not open by saying what the question
    was read as, which the line says too."""

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
    if not said_as:
        text = re.sub(r"^_Understood as `[^`]*`_\n\n", "", text)
    return focused(question, text), status


def reply(
    spec: SpecDocument,
    question: str,
    vocabulary: Vocabulary,
    llm: Optional[str] = None,
) -> str:
    """The answer to 'question', as Markdown, opening with what it was read as"""

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

    filler = {w.upper() for w in FILLER.findall(question)}
    acronyms = {word.upper() for _, _, word in acronyms_of(question)} - filler
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
