# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
Ask the model questions, interactively, as of an expert who answers at once

    senfd-ask
    > opcode of zone append
    > cdw12 of write
    > FUA
    > log page 1Fh

A question is understood without a language model: by its words, as "opcode
of", "cdw12 of", "feature", "log page" or "section", by an identifier, as
"1Fh", or by an acronym or a name the model has. Each answer says what the
question was understood as, so a question understood otherwise than meant
shows, and is the answer of a query of the model, with the figures it cites.
Names, acronyms and the words of questions complete as they are typed.

An answer is shown only when it mentions every term of the question that
names something, so a question of something the model does not have is
answered by saying so, rather than with what was found for its other words.

With ``--llm URL``, a language model served there, as by llama.cpp's
``llama-server``, understands the question instead. Its output is
constrained, by a JSON schema, to the name of a query and its argument; it
writes no part of the answer, so it can state no field, bit or opcode the
model does not have. A lookup that finds nothing, or nothing mentioning the
question's terms, is said to it, and it chooses again, three times at most.

The prompt and the rendering are of the extra 'ask', ``pip install
senfd[ask]``; without it, questions are read line by line and the answers
printed as Markdown.
"""

import argparse
import json
import re
import sys
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Set, Tuple

import senfd.query
from senfd.documents.spec import Bits, SpecDocument, alias

HELP = """\
**Ask about a command, a feature, a log page, a structure, a register or a field.**

| Ask | As |
|---|---|
| a command, with its dwords | `write`, `zone append`, `opcode of sanitize` |
| one dword of a command | `cdw12 of write`, `dword 10 of get log page` |
| a feature or a log page | `feature 07h`, `feature number of queues`, `log page 1Fh` |
| what an identifier is | `1Fh` |
| a structure or a register | `structure identify controller`, `CC`, `CSTS` |
| a field, everywhere it is | `FUA`, `search storage tag` |
| a section | `section 5.2.6` |
| what the documents may have wrong | `errata`, `errata nvm` |

Press Tab to complete a name or an acronym, `help` for this, Ctrl-D to leave.
"""

WORDS = [
    "opcode of ",
    "cdw10 of ",
    "cdw11 of ",
    "cdw12 of ",
    "cdw13 of ",
    "cdw14 of ",
    "cdw15 of ",
    "feature ",
    "log page ",
    "structure ",
    "search ",
    "section ",
    "errata",
    "help",
]

# The words a question may be phrased in, and that name nothing
FILLER = re.compile(
    r"\b(what|which|where|is|are|the|of|in|a|an|does|do|show|me|tell|about|"
    r"bits?|fields?|command|commands|register|please|give|hold|holds|for)\b|\?",
    re.IGNORECASE,
)


@dataclass
class Understood:
    """A question as a query of the model: its name and its arguments"""

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


@dataclass
class Vocabulary:
    """The names and acronyms of the model, which a question may name"""

    commands: Set[str] = field(default_factory=set)
    features: Set[str] = field(default_factory=set)
    log_pages: Set[str] = field(default_factory=set)
    structures: Set[str] = field(default_factory=set)
    acronyms: Set[str] = field(default_factory=set)
    registers: Set[str] = field(default_factory=set)

    @classmethod
    def of(cls, spec: SpecDocument) -> "Vocabulary":
        vocabulary = cls()

        def acronyms(fields: Iterable[Bits]):
            for f in fields:
                if f.acronym:
                    vocabulary.acronyms.add(f.acronym)
                acronyms(f.fields)

        for command_set in spec.command_sets.values():
            for cmd in command_set.commands.values():
                vocabulary.commands.add(cmd.name)
                for d in [*cmd.sqe, *cmd.cqe]:
                    acronyms(d.fields)
                for operation in cmd.operations:
                    for d in [*operation.sqe, *operation.cqe]:
                        acronyms(d.fields)
        for f in spec.features.values():
            vocabulary.features.add(f.name)
            for d in [*f.sqe, *f.cqe]:
                acronyms(d.fields)
        vocabulary.log_pages.update(p.name for p in spec.log_pages.values())
        for s in spec.structures:
            vocabulary.structures.add(s.name)
            acronyms(s.fields)
            # A register is asked for by its acronym, "CC" of "CC - ..."
            head, dash, _ = s.name.partition(" - ")
            if dash and head.isupper():
                vocabulary.acronyms.add(head)
                vocabulary.registers.add(head)
        return vocabulary

    def words(self) -> List[str]:
        """What completes a question: its words, then every name and acronym"""

        names = self.commands | self.features | self.log_pages | self.structures
        return WORDS + sorted(names, key=str.lower) + sorted(self.acronyms)

    def is_command(self, name: str) -> bool:
        return alias(name) in {alias(c) for c in self.commands}


def words_of(text: str) -> str:
    """'text' as lowercase words, each between spaces, for whole-word matching"""

    return " " + " ".join(re.findall(r"[a-z0-9]+", text.lower())) + " "


def spot(
    question: str, vocabulary: Vocabulary, only: Optional[str] = None
) -> Optional[Tuple[str, str]]:
    """The longest name of the model the question names, with its kind, or of
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
    # dword asks of, whatever command's name its words also make, "Shutdown"
    if registers and not dword:
        return Understood("register", registers[0])
    if named and named[0] == "command":
        return Understood("command", named[1], int(dword[1]) if dword else None)
    rest = " ".join(terms(text))
    if asks_command and not named and not registers and rest:
        argument = command_named(text, vocabulary) or rest
        return Understood("command", argument, int(dword[1]) if dword else None)
    if registers:
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


def answer(
    spec: SpecDocument,
    understood: Understood,
    vocabulary: Optional[Vocabulary] = None,
) -> List[str]:
    """The Markdown answering 'understood'; a command named with more than its
    name, as "Admin Track Send", is the command its name names"""

    if understood.query == "command" and vocabulary is not None:
        lines = senfd.query.command(
            spec, understood.argument, understood.dword, markdown=True
        )
        named = spot(understood.argument, vocabulary)
        if nothing(lines) and named and named[0] == "command":
            understood.argument = named[1]
        else:
            return lines

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


def nothing(lines: List[str]) -> bool:
    return not lines or lines[0].startswith(("No ", "Nothing named", "Give "))


def ambiguous(lines: List[str]) -> bool:
    """Whether 'lines' list what a name matches rather than answer, as
    "92 structures; be more specific" """

    return bool(lines) and bool(re.match(r"\d+ [a-z ]+; be more specific", lines[0]))


def bullets(lines: List[str]) -> List[str]:
    return lines if nothing(lines) else [f"- {line}" for line in lines]


def heading(lines: List[str]) -> str:
    return next((line for line in lines if line.strip()), "")


SEVERAL = "several commands"
# What asks of a command: its opcode or a dword of it
ASKS_COMMAND = r"\b(?:opcodes?|opc|cdw\d*|(?:command )?dword\s*\d+|dw\d+)\b"
DWORD = r"\b(?:cdw|dword|command dword|dw)\s*(\d+)\b"


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

    if registers and not dword:
        head = name.partition(" - ")[0] if name else None
        return None if kind == "register" and head in registers else registers[0]
    kinds = [
        of
        for word, of in (
            (r"\blog ?pages?\b|\blid\b", "log_page"),
            (r"\bfeatures?\b|\bfid\b", "feature"),
            (r"\bstructures?\b", "structure"),
        )
        # "the log page identifier in Get Log Page" asks of the command
        if re.search(word, lower) and not command
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
    if understood.query in ("feature", "log_page", "structure", "register"):
        if name is None:
            return named[1]
        head = name.partition(" - ")[0]
        return None if alias(named[1]) in (alias(name), alias(head)) else named[1]
    text = words_of(" ".join(lines))
    return None if words_of(named[1]) in text else named[1]


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
                kind = "register"
            return kind, match[1]
    return None


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


REVISION = (
    r"(?i)\b(?:nvme|nvm express|base|revision|rev|version|specification|spec)"
    r"\s+v?\d+(?:\.\d+)+[a-z]?\b"
)

# Words of a question that name nothing the answer must mention
GENERIC = set(
    """
    what which where when who how is are was the of in on a an to for and or by
    with does do did show me tell about please give hold holds held there it its
    this that these those be can could would should take takes taken use used
    bit bits field fields byte bytes offset command commands register registers
    structure structures data log page pages feature features identifier
    identifiers opcode opcodes dword dwords value values set select selects
    selected describe describes described mean means stand stands name named
    called contain contains have has ask asks enable enables entry entries
    specification spec nvme nvm express admin section sections errata erratum
    id ids fid lid opc hey hi hello thanks thank you i we my our need want know
    find just also any search at as if into from not no than then up out over under per
    via whose whom
    """.split()
)


def terms(question: str) -> List[str]:
    """The terms of 'question' that name something, without a plural's 's'"""

    # "0x07" is "07h", as the model writes it; "CSTS.RDY" is CSTS and RDY; and
    # "NVMe 2.0" is a revision, not a section the answer must mention
    question = re.sub(REVISION, "", question)
    question = re.sub(
        r"\b0x([0-9A-Fa-f]{1,2})\b", lambda m: m[1].upper() + "h", question
    )
    words = re.findall(
        r"[A-Za-z][A-Za-z0-9]*|\d+(?:\.\d+)+|[0-9A-Fa-f]{1,2}h\b", question
    )
    found = []
    for word in words:
        key = word.lower()
        if key in GENERIC or len(key) < 2:
            continue
        # A plural's 's', not an acronym's, as of "CSTS"
        found.append(key if word.isupper() else re.sub(r"(?<=[a-z]{3})s$", "", key))
    return found


def unmentioned(question: str, lines: List[str]) -> List[str]:
    """The terms of 'question' that the answer 'lines' does not mention"""

    text = " ".join(lines).lower()
    return [
        t
        for t in terms(question)
        if not re.search(rf"(?<![a-z0-9]){re.escape(t)}s?(?![a-z0-9])", text)
    ]


def reply(
    spec: SpecDocument,
    question: str,
    vocabulary: Vocabulary,
    llm: Optional[str] = None,
) -> str:
    try:
        text, _ = respond(spec, question, vocabulary, llm)
    except (OSError, ValueError, KeyError, IndexError) as exc:
        if llm is None:
            raise
        return f"The language model at {llm} did not choose a lookup: {exc}"
    return text


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
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": question},
        ]
        for _ in range(tries):
            understood = choose(llm, messages)
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
            f"Not in the model{why}, so this is not known. "
            "`help` says what can be asked."
        ), tried
    return f"_Understood as `{understood}`_\n\n" + "\n".join(lines), tried


QUERIES = {
    "command": "a command by name, with its dwords and opcode: 'write', 'zone append'",
    "feature": "a feature by identifier, '07h', or by name",
    "log_page": "a log page by identifier, '02h', or by name",
    "structure": "a data structure by name: 'identify controller'",
    "register": "a register by its acronym: 'CC', 'CSTS', 'CAP'",
    "search": "fields by acronym, 'FUA', or by name, and commands, features, "
    "log pages and structures by a word of their name",
    "section": "what a section describes, by number: '5.2.6'",
    "unknown": "the question is not about the NVMe specifications",
}

SYSTEM = (
    "You choose one lookup in a model of the NVMe specifications that answers "
    "the user's question. You never answer yourself. The lookups are:\n"
    + "\n".join(f"- {name}: {what}" for name, what in QUERIES.items())
    + "\n'dword' is for a command only, as 12 for CDW12, else null. Examples:\n"
    "- 'Which bit of CDW12 of Write is FUA?' -> command, 'write', 12\n"
    "- 'What is the opcode of Get Log Page?' -> command, 'get log page', null\n"
    "- 'Which feature is Number of Queues?' -> feature, 'number of queues', null\n"
    "- 'Which bits of CC select the arbitration mechanism?' -> register, 'CC', null\n"
    "- 'What does STC stand for?' -> search, 'STC', null\n"
    "- 'What is the capital of France?' -> unknown, '', null\n"
    "If you are told a lookup found nothing, or nothing mentioning the "
    "question, choose another; if none fits, choose unknown."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"enum": list(QUERIES)},
        "argument": {"type": "string"},
        "dword": {"type": ["integer", "null"]},
    },
    "required": ["query", "argument", "dword"],
}


def choose(url: str, messages: List[dict]) -> Understood:
    """The lookup a language model at 'url' chooses, constrained to SCHEMA"""

    body = {
        "messages": messages,
        "temperature": 0,
        "response_format": {"type": "json_schema", "json_schema": {"schema": SCHEMA}},
    }
    request = urllib.request.Request(
        f"{url.rstrip('/')}/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        content = json.load(response)["choices"][0]["message"]["content"]
    chosen = json.loads(content)
    dword = chosen.get("dword")
    return Understood(
        chosen["query"],
        chosen.get("argument", ""),
        dword if chosen["query"] == "command" and dword else None,
    )


def interact(spec: SpecDocument, llm: Optional[str] = None) -> int:
    vocabulary = Vocabulary.of(spec)
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.completion import FuzzyWordCompleter
        from prompt_toolkit.history import InMemoryHistory
        from rich.console import Console
        from rich.markdown import Markdown
    except ImportError:
        print(HELP)
        while True:
            try:
                question = input("> ")
            except EOFError:
                return 0
            print(reply(spec, question, vocabulary, llm))

    console = Console()
    console.print(Markdown(HELP))
    words = vocabulary.words()
    session: PromptSession = PromptSession(
        completer=FuzzyWordCompleter(words, WORD=True),
        complete_while_typing=True,
        history=InMemoryHistory(),
        bottom_toolbar=(
            f" {len(vocabulary.commands)} commands, {len(vocabulary.features)} "
            f"features, {len(vocabulary.log_pages)} log pages, "
            f"{len(vocabulary.structures)} structures. Tab completes; help."
        ),
    )
    while True:
        try:
            question = session.prompt("ask> ")
        except (EOFError, KeyboardInterrupt):
            return 0
        if question.strip():
            console.print(Markdown(reply(spec, question, vocabulary, llm)))


def show(markdown: str, raw: bool = False) -> None:
    """Print 'markdown' rendered, where the extra 'ask' is installed and not
    'raw', else as it is"""

    try:
        if raw:
            raise ImportError
        from rich.console import Console
        from rich.markdown import Markdown
    except ImportError:
        print(markdown)
        return
    Console().print(Markdown(markdown))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("question", nargs="*", help="Answer this, and leave")
    parser.add_argument(
        "--spec",
        type=Path,
        default=None,
        help=f"The merged model (default: {senfd.query.default_spec_path()})",
    )
    parser.add_argument(
        "--raw", action="store_true", help="Print an answer as Markdown, unrendered"
    )
    parser.add_argument(
        "--llm",
        default=None,
        metavar="URL",
        help="Have the language model served at URL understand the questions",
    )
    args = parser.parse_args(argv)
    try:
        spec = senfd.query.load(args.spec)
    except OSError as exc:
        print(f"senfd-ask: no model to answer from: {exc}", file=sys.stderr)
        return 1
    if args.question:
        show(
            reply(spec, " ".join(args.question), Vocabulary.of(spec), args.llm),
            args.raw,
        )
        return 0
    return interact(spec, args.llm)


if __name__ == "__main__":
    raise SystemExit(main())
