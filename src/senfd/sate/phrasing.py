# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
The language of questions: their words, the forms and the common questions
they take, and the terms of a question that name something
"""

import re
from typing import List, Tuple


# FORMS is the table of question forms. HELP adds the keys of the terminal
# session, which sate-web does not show, since sate-web has other keys
FORMS = """\
sate answers these forms of question. Each answer cites the figure that it
comes from.

| Question | sate answers with |
|---|---|
| `opcode of sanitize` | the opcode of Sanitize |
| `fid of arbitration` | the identifier and fields of feature Arbitration |
| `lpi of error information` | the identifier and fields of Error Information |
| `cns of identify controller` | each CNS value that names Identify Controller |
| `dwords of write` | the opcode, command-dwords and fields |
| `cdw12 of write` | the fields of Command Dword 12 of Write |
| `structure identify controller` | the fields of Identify Controller |
| `log page 1Fh` | the name of log page 1Fh and its fields |
| `feature 07h` | the name of feature 07h and its fields |
| `CNS 05h` | each entry for the CNS value 05h |
| `status code 82h` | each status code 82h, and each range that includes 82h |
| `what does status 0x4281 mean?` | what the SCT and SC in status 4281h mean |
| `1Fh` | each feature, log page, status code and CNS value 1Fh |
| `CSTS` | the offset and the fields of the CSTS register |
| `FUA` | each field with the acronym FUA |
| `search storage tag` | each name that contains "storage tag" |
| `describe cdw12 of write` | cdw12 of Write, with field descriptions |
| `section 5.2.6` | the subsections and figures of section 5.2.6 |
| `errata` | the candidate errata that senfd found |
"""
HELP = (
    FORMS
    + """
Tab completes a name or an acronym. `?` shows the common questions. `help`
or F1 shows this table. Ctrl-D ends the session.
"""
)


WORDS = [
    "describe ",
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
    "status code ",
    "cns ",
    "search ",
    "section ",
    "errata",
    "help",
]


# The common questions, as typed and as shown: an example, its names in
# braces filled from the data model, so that what to swap is a real name
QUESTIONS = [
    ("what is the opcode of ", "what is the opcode of {command}?"),
    ("which bit of cdw", "which bit of cdw{dword} of {command} is {acronym}?"),
    ("which bits of cdw", "which bits of cdw{dword} of {command} are {acronyms}?"),
    ("what are the fields of the ", "what are the fields of the {structure}?"),
    ("which feature is ", "which feature is {feature}?"),
    ("which log page is ", "which log page is {log_page}?"),
    ("what is status code ", "what is status code {code}?"),
    ("what does status ", "what does status {status} mean?"),
    ("what does sct ", "what does SCT {sct} SC {sc} mean for {command}?"),
]


# The words after which a question names a thing of one kind
KINDS_AFTER = [
    (re.compile(r"log page(?: is)? $", re.I), "log page"),
    (re.compile(r"\b(?:lid|lpi|log page identifier) of $", re.I), "log page"),
    (re.compile(r"feature(?: is)? $", re.I), "feature"),
    (re.compile(r"\b(?:fid|feature identifier) of $", re.I), "feature"),
    (re.compile(r"\bcns(?: values?)? of $", re.I), "cns"),
    (re.compile(r"\b(?:register|offset of) $", re.I), "register"),
    (re.compile(r"(?:structure|fields of(?: the)?) $", re.I), "structure"),
    (re.compile(r"(?:opcode|cdw\d+|dword \d+|dwords|cdws) of $", re.I), "command"),
    (re.compile(r"\b(?:is|are) $", re.I), "acronym"),
]


# The words of questions, as the input line shows them recognised
QUESTION_WORDS = re.compile(
    r"\b(?:describe|explain|opcode of|(?:cdw|dword ?)\d+(?: of)?|feature|log page|"
    r"structure|register|status code(?: type)?|cns|section|search|errata|help)\b",
    re.I,
)


# The words a question may be phrased in, and that name nothing
FILLER = re.compile(
    r"\b(what|which|where|is|are|the|of|in|a|an|does|do|show|me|tell|about|"
    r"bits?|fields?|command|commands|register|please|give|hold|holds|for)\b|\?",
    re.IGNORECASE,
)


# What asks of a command: its opcode or a dword of it
ASKS_COMMAND = r"\b(?:opcodes?|opc|cdw\d*|(?:command )?dword\s*\d+|dw\d+)\b"


DWORD = r"\b(?:cdw|dword|command dword|dw)\s*(\d+)\b"


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
    selected describe describes described explain explains explained mean means
    stand stands name named
    called contain contains have has ask asks enable enables entry entries
    specification spec nvme nvm mi express admin section sections errata erratum
    id ids fid lid lpi opc hey hi hello thanks thank you i we my our need want know
    find just also any search at as if into from not no than then up out over under per
    via whose whom many much report reports reported reporting indicate indicates
    return returns returned
    """.split()
)


def words_of(text: str) -> str:
    """'text' as lowercase words, each between spaces, for whole-word matching"""

    return " " + " ".join(re.findall(r"[a-z0-9]+", text.lower())) + " "


def terms(question: str) -> List[str]:
    """The terms of 'question' that name something, without a plural's 's'"""

    # "0x07" is "07h", as the data model writes it; "CSTS.RDY" is CSTS and RDY; and
    # "NVMe 2.0" is a revision, not a section the answer must mention
    question = re.sub(REVISION, "", question)
    question = re.sub(r"\b0x([0-9A-Fa-f]+)\b", lambda m: m[1].upper() + "h", question)
    words = re.findall(r"[A-Za-z][A-Za-z0-9]*|\d+(?:\.\d+)+|[0-9A-Fa-f]+h\b", question)
    found = []
    for word in words:
        key = word.lower()
        term = key if word.isupper() else singular(key)
        if key in GENERIC or term in GENERIC or len(key) < 2:
            continue
        found.append(term)
    return found


def singular(word: str) -> str:
    """'word' without a plural's 's': "queues" is "queue", while "status",
    "address" and "analysis" are not plurals"""

    return re.sub(r"(?<=[a-z]{2}[^siu])s$", "", word)


# An acronym as written in a question: "FUA", "IPM.PMT", or "CSTS.RDY", which
# is also CSTS and RDY
ACRONYM = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:\.[A-Za-z][A-Za-z0-9]*)*")


def acronyms_of(text: str) -> List[Tuple[int, int, str]]:
    """The words of 'text' that may be acronyms, as (start, end, word): each
    dotted word whole, then each of its parts"""

    found = []
    for m in ACRONYM.finditer(text):
        found.append((m.start(), m.end(), m[0]))
        if "." in m[0]:
            at = m.start()
            for part in m[0].split("."):
                found.append((at, at + len(part), part))
                at += len(part) + 1
    return found
