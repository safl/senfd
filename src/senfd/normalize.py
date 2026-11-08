# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
Normalisation of the tables and captions of the specification documents

The documents vary in how they write the same thing: a caption's dash with or
without spaces, "Definition" for "Description", a footnote marker on a column
header, the columns in another order. The functions here map those variants to
one form, and say what they did as a diagnostic, so that the variance can be
reported, and fixed in the documents, without stopping the output.
"""

import re
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel

from senfd.documents.base import TRANSLATION_TABLE, Model


class Diagnostic(Model):
    """
    Something about a figure that senfd normalised, or could not make sense of

    A 'note' is a variant senfd normalised; nothing is lost. A 'warning' is
    something left out of the output, as a row whose range is not a range.
    """

    figure_nr: Optional[int] = None
    """The number of the figure, where it is known"""
    severity: str
    """'note' or 'warning'"""
    code: str
    """What kind it is, as "figure-not-modelled" or 'dwords-unassigned'"""
    message: str
    """What was found, with the document and the figure, said for a person"""


def note(code: str, message: str) -> Diagnostic:
    return Diagnostic(severity="note", code=code, message=message)


def warning(code: str, message: str) -> Diagnostic:
    return Diagnostic(severity="warning", code=code, message=message)


def normalize_text(text: str) -> str:
    """Typographic characters as their plain equivalents, whitespace as one space"""

    return re.sub(r"\s+", " ", text.translate(TRANSLATION_TABLE)).strip()


def normalize_caption(text: str) -> Tuple[str, List[Diagnostic]]:
    """A caption with its parts separated by ' - ', and whitespace collapsed"""

    diagnostics = []
    # The parts are separated by an en or em dash, a hyphen being part of a word
    # as in "Self-test"; a hyphen with a space on one side only is a separator
    # too
    if re.search(r"\S[–—]|[–—]\S|\w -\w|\w- \w", text):
        diagnostics.append(
            note("caption-dash", f"Caption dash not spaced: '{normalize_text(text)}'")
        )
    text = re.sub(r"\s*[–—]\s*|(?<=\w) -(?=\w)|(?<=\w)- (?=\w)", " - ", text)
    return normalize_text(text), diagnostics


# Column headers by their canonical name; a header is matched after normalising
# it and stripping any footnote marker
COLUMNS: Dict[str, List[str]] = {
    "bits": ["bits", "bit"],
    "bytes": ["bytes", "byte"],
    "description": ["description", "definition"],
    "name": ["name", "field name", "field", "term", "acronym"],
    "value": ["value", "code", "status code value", "level"],
    "cns_value": ["cns value"],
    "opcode": ["combined opcode", "combined opcode value", "opcode value", "opcode"],
    "command": ["command", "nvme command", "admin command"],
    "reference": ["reference", "reference section"],
    "om": ["o/m", "m/o"],
    "identifier": ["feature identifier", "log page identifier", "identifier"],
    "log_page_name": ["log page name"],
    "transition": ["state transition", "state transitions"],
    "transition_condition": ["transition condition"],
}

SYNONYMS: Dict[str, str] = {
    synonym: canonical
    for canonical, synonyms in COLUMNS.items()
    for synonym in synonyms
}


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def normalize_header(text: str) -> Tuple[str, List[Diagnostic]]:
    """The canonical name of a column header, or a name made from its text"""

    header = normalize_text(text).lower()
    if header in SYNONYMS:
        return SYNONYMS[header], []

    # A footnote marker: "O/M1", "NSID 2", "Combined Opcode1"
    stripped = re.sub(r"(?<=[a-z/)])\s*\d+$", "", header)
    if stripped in SYNONYMS:
        return SYNONYMS[stripped], []

    return slug(stripped) or "", []


# Shapes by the columns they need; the first shape whose columns a header has
SHAPES: List[Tuple[str, List[str]]] = [
    ("layout", ["bits", "description"]),
    ("layout", ["bytes", "description"]),
    ("layout", ["bits", "name"]),
    ("opcode", ["opcode", "command"]),
    ("value", ["cns_value", "description"]),
    ("value", ["identifier", "description"]),
    ("value", ["identifier", "log_page_name"]),
    ("value", ["identifier", "feature_name"]),
    ("value", ["value", "description"]),
    ("transition", ["transition_condition"]),
]


def shape_of(columns: List[str]) -> Optional[str]:
    for shape, needs in SHAPES:
        if all(need in columns for need in needs):
            return shape
    if any("requirement" in column for column in columns) or {
        "i_o",
        "admin",
    } <= set(columns):
        return "requirement"
    if "name" in columns and "description" in columns:
        return "value"
    # A value with a name, as "Directive Operation Value" and "... Name"
    if any(c.endswith("_value") for c in columns) and any(
        c.endswith("_name") or c == "directive" for c in columns
    ):
        return "value"
    return None


REGEX_RANGE = re.compile(r"^(?:(?P<upper>\d+)\s*:\s*)?(?P<lower>\d+)$")


class Range(BaseModel):
    """
    The bits or bytes of a field, as 'upper' and 'lower'; a range the document
    gives by a formula, such as "(N*16)+15:N*16", has the formula as its text
    and neither bound
    """

    unit: str
    text: str
    upper: Optional[int] = None
    lower: Optional[int] = None


def parse_range(unit: str, text: str) -> Optional[Range]:
    """
    The range of 'text'; a range that is not a number, as "n/a" or a formula,
    has its text and neither bound, and empty text is no range
    """

    text = normalize_text(text)
    match = REGEX_RANGE.match(text)
    if match:
        lower = int(match["lower"])
        upper = int(match["upper"]) if match["upper"] else lower
        return Range(unit=unit, text=text, upper=upper, lower=lower)
    return Range(unit=unit, text=text) if text else None


# A footnote marker can follow the acronym, as in "Name (ACR) 1:" or "(ACR)1, 3:";
# without an acronym, digits at the end are the name's, as in "Entry 1:"
REGEX_FIELD = re.compile(
    r"^(?P<name>[^:()]*?[^\s:()])\s*(?:\((?P<acronym>[^()]+)\)"
    r"(?:\s*\d+(?:,\s*\d+)*)?)?\s*(?::\s*(?P<rest>.*))?$"
)


REGEX_FIELD_NO_COLON = re.compile(
    r"^(?P<name>[^:()]*?[^\s:()])\s*\((?P<acronym>[A-Z][A-Z0-9_]*)\)\s+(?P<rest>[A-Z].*)$"
)


def parse_field_description(text: str) -> Tuple[Optional[str], Optional[str], str]:
    """
    The name, acronym and description of a field, from the text of its
    description cell: "Name (ACRONYM): description", the description going on in
    the paragraphs after the first
    """

    first, _, more = text.strip().partition("\n")
    first = normalize_text(first)
    more = more.strip()
    match = REGEX_FIELD.match(first)
    if not match:
        # "Name (ACR) The description...", the colon left out
        match = REGEX_FIELD_NO_COLON.match(first)
    if not match or len(match["name"]) > 80:
        return None, None, "\n".join(p for p in [first, more] if p)

    name = match["name"].strip()
    if match["rest"] is None and not match["acronym"] and not is_name(name):
        # A sentence, as "Ignored by the controller", describes and names nothing
        return None, None, "\n".join(p for p in [first, more] if p)

    rest = (match["rest"] or "").strip()
    description = "\n".join(p for p in [rest, more] if p)
    return name, match["acronym"], description


def is_name(text: str) -> bool:
    """Whether 'text', with neither colon nor acronym after it, is a name rather
    than a sentence: "Reserved", "Vendor Specific", but not "Refer to the NVM
    Command Set Specification" """

    words = text.split()
    small = {"a", "an", "and", "by", "for", "in", "is", "of", "or", "the", "to"}
    return (
        len(words) <= 4
        and not text.endswith(".")
        and all(w[0].isupper() or w[0].isdigit() or w in small for w in words)
        and sum(w in small for w in words) <= 1
    )


class Subject(BaseModel):
    """
    What a figure describes, from its caption

    'kind' is one of the kinds of CAPTIONS, or "other" for a caption of none of
    them; 'name' is the command, data structure, log page or other thing named.
    """

    kind: str
    name: Optional[str] = None
    lower: Optional[int] = None
    upper: Optional[int] = None
    condition: Optional[str] = None
    offset: Optional[str] = None
    qualifier: Optional[str] = None
    scope: Optional[str] = None


NAME = r"(?P<name>.+?)"
DWORDS = (
    r"(?:Command )?Dwords? (?P<lower>\d+)"
    r"(?:(?:,| and|, and| to| -)? (?:Command )?(?:Dword )?(?P<upper>\d+))?"
)

# The kinds of captions, by the patterns of the captions; the first kind with a
# pattern matching the normalised caption is the subject's kind
CAPTIONS: List[Tuple[str, List[str]]] = [
    ("example", [r"^Example\b.*", r".*\bExample$"]),
    (
        "opcodes",
        [r"^Opcodes for " + NAME + r"(?: Commands| Command Set(?: Commands)?)?$"],
    ),
    (
        "command_dword",
        [
            r"^"
            + NAME
            + r" - "
            + DWORDS
            + r"(?: if (?P<condition>.+?))?(?: - (?P<qualifier>.+))?$",
            r"^" + DWORDS + r"(?: - (?P<qualifier>.+))?$",
        ],
    ),
    (
        "completion_dword",
        [
            r"^(?:" + NAME + r" - )?Completion Queue Entry Dword (?P<lower>\d+)"
            r"(?: (?:if|when) (?P<condition>.+))?$"
        ],
    ),
    ("data_pointer", [r"^" + NAME + r" - Data Pointer$"]),
    ("metadata_pointer", [r"^" + NAME + r" - Metadata Pointer$"]),
    ("data_buffer", [r"^" + NAME + r" - Data Buffer$"]),
    (
        "management_dword",
        [r"^" + NAME + r"(?: -)? NVMe Management Dword (?P<lower>\d+)$"],
    ),
    (
        "pcie_request_dword",
        [r"^" + NAME + r"(?: -)? PCIe Request Dword (?P<lower>\d+)$"],
    ),
    (
        "register",
        [r"^Offset (?P<offset>[0-9A-Fa-f]+h)(?:\s*:\s*|\s+-\s+)" + NAME + r"$"],
    ),
    ("cns_values", [r"^(?:" + NAME + r" - )?CNS Values$"]),
    (
        "feature_identifiers",
        [
            r"^Feature Identifiers(?: - " + NAME + r")?$",
            r"^" + NAME + r" - Feature Identifiers$",
        ],
    ),
    ("log_page_identifiers", [r"^(?:" + NAME + r" - )?Log Page Identifiers$"]),
    (
        "status_values",
        [
            r"^(?:" + NAME + r" - )?(?:(?P<qualifier>.*?) )?Status (?:Values?|Codes?)"
            r"(?:, (?P<scope>.+))?$",
            r"^Status Code - (?P<qualifier>.+) Values$",
        ],
    ),
    (
        "requirements",
        [
            r"^(?:" + NAME + r" - )?(?P<qualifier>.+?) Support(?: Requirements)?$",
            r"^" + NAME + r" Requirements$",
        ],
    ),
    ("log_page", [r"^" + NAME + r" Log Page(?: Entry| for (?P<qualifier>.+))?$"]),
    (
        "data_structure",
        [
            r"^"
            + NAME
            + r"(?: -)? (?:Data )?Structure(?: Entry| for (?P<qualifier>.+)|, (?P<qualifier2>.+))?$"
        ],
    ),
]


def parse_caption(caption: str) -> Subject:
    """The subject of the normalised caption 'caption'"""

    for kind, patterns in CAPTIONS:
        for pattern in patterns:
            match = re.match(pattern, caption, flags=re.IGNORECASE)
            if not match:
                continue
            groups = {k: v for k, v in match.groupdict().items() if v is not None}
            if "qualifier2" in groups:
                groups["qualifier"] = groups.pop("qualifier2")
            for bound in ("lower", "upper"):
                if bound in groups:
                    groups[bound] = int(groups[bound])
            if "lower" in groups and "upper" not in groups:
                groups["upper"] = groups["lower"]
            return Subject(kind=kind, **groups)
    return Subject(kind="other", name=caption)
