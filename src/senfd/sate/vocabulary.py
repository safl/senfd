# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""What the data model names, which a question may name: the names of its
commands, features, log pages and structures, and the acronyms of their
fields, by the thing and the dword they are of"""

import difflib
import re
from dataclasses import dataclass, field
from functools import cached_property
from typing import Dict, Iterable, List, Optional, Set, Tuple

from senfd.sate.phrasing import GENERIC
from senfd.documents.spec import Bits, Dwords, SpecDocument, document_name


def spaced(text: str) -> str:
    """'text' as its words in lowercase, with a space before and after each"""

    return " " + " ".join(re.findall(r"[a-z0-9/]+", text.lower())) + " "


# What fields are of: a thing by its name in lowercase and, of a command or
# a feature, one dword of it, or None for all of it
Of = Tuple[str, Optional[int]]


@dataclass
class Vocabulary:
    """The names and acronyms of the data model, which a question may name"""

    commands: Set[str] = field(default_factory=set)
    features: Set[str] = field(default_factory=set)
    log_pages: Set[str] = field(default_factory=set)
    structures: Set[str] = field(default_factory=set)
    acronyms: Set[str] = field(default_factory=set)
    registers: Set[str] = field(default_factory=set)
    # The structures that a CNS value returns, by a CNS entry naming them
    cns: Set[str] = field(default_factory=set)
    # The names of the entries of the tables of values, as "RDMA Invalid
    # HSQSIZE"; of features and log pages, those are their names above
    values: Set[str] = field(default_factory=set)
    # The tables of other values: the title, the headers of the columns of
    # their codes, and the names, acronyms and symbols of the entries
    tables: List[Tuple[str, Set[str], Set[str]]] = field(default_factory=list)
    # The acronyms and symbols of the entries of the tables of other values,
    # as "SQ0TDBL" of a table of properties
    symbols: Set[str] = field(default_factory=set)
    # The words of the captions and section titles of each document, by its
    # short name as a citation gives it, "Boot 1.4"
    documents: Dict[str, str] = field(default_factory=dict)
    # The acronyms of the fields of a thing, in the order of its figures
    fields: Dict[Of, List[str]] = field(default_factory=dict)

    @classmethod
    def of(cls, spec: SpecDocument) -> "Vocabulary":
        vocabulary = cls()
        for command_set in spec.command_sets.values():
            for cmd in command_set.commands.values():
                vocabulary.commands.add(cmd.name)
                vocabulary.add_dwords(cmd.name, cmd.sqe, cmd.cqe)
                for operation in cmd.operations:
                    vocabulary.add_dwords(cmd.name, operation.sqe, operation.cqe)
        for feature in spec.features.values():
            vocabulary.features.add(feature.name)
            vocabulary.add_dwords(feature.name, feature.sqe, feature.cqe)
        vocabulary.log_pages.update(page.name for page in spec.log_pages.values())
        for structure in spec.structures:
            vocabulary.structures.add(structure.name)
            # A register is asked for by its acronym, "CC" of "CC - ..."
            head, dash, _ = structure.name.partition(" - ")
            if dash and head.isupper():
                vocabulary.acronyms.add(head)
                vocabulary.registers.add(head)
                vocabulary.add_fields(
                    structure.fields,
                    (structure.name.lower(), None),
                    (head.lower(), None),
                )
            else:
                vocabulary.add_fields(structure.fields, (structure.name.lower(), None))
        titled: Dict[str, List[str]] = {}
        captioned = [(s.source, s.name) for s in spec.structures] + [
            (v.source, v.name or "") for v in spec.values
        ]
        for source, caption in captioned:
            titled.setdefault(document_name(source.document), []).extend(
                [caption, source.section_title or ""]
            )
        vocabulary.documents = {
            name: spaced(" ".join(texts)) for name, texts in titled.items()
        }
        for table in spec.values:
            if table.kind != "other":
                continue
            marks = {
                mark
                for entry in table.entries
                for mark in (entry.columns.get("acronym"), entry.columns.get("symbol"))
                if mark
            }
            vocabulary.symbols |= marks
            vocabulary.tables.append(
                (
                    table.name or "",
                    {e.value_column.replace("_", " ") for e in table.entries},
                    {e.name for e in table.entries if e.name} | marks,
                )
            )
        named_elsewhere = (
            "feature_identifiers",
            "log_page_identifiers",
            "requirements",
        )
        vocabulary.values = {
            entry.name
            for table in spec.values
            if table.kind not in named_elsewhere
            for entry in table.entries
            # One word, as "FOO" of a table of acronyms, is a word of names
            if entry.name and len(entry.name.split()) > 1
        }
        returned = [
            spaced(entry.description or "")
            for table in spec.values
            if table.kind == "cns_values"
            for entry in table.entries
        ]
        for name in vocabulary.structures:
            head, dash, rest = name.partition(" - ")
            # "Identify - Identify Namespace" is named in its entry by its rest;
            # one word, as "Format", is a word of other entries' descriptions
            named = spaced(rest if dash and head == "Identify" else name)
            if named.count(" ") > 2 and any(named in text for text in returned):
                vocabulary.cns.add(name)
        return vocabulary

    def add_dwords(self, name: str, sqe: List[Dwords], cqe: List[Dwords]) -> None:
        """The fields of the dwords of the command or feature 'name'"""

        whole: Of = (name.lower(), None)
        for dwords in sqe:
            numbers: List[Of] = [
                (name.lower(), n) for n in range(dwords.lower, dwords.upper + 1)
            ]
            self.add_fields(dwords.fields, *numbers, whole)
        for dwords in cqe:
            self.add_fields(dwords.fields, whole)

    def add_fields(self, fields: Iterable[Bits], *of: Of) -> None:
        """The acronyms of 'fields', and of the fields within them, as of each
        of 'of'"""

        for f in fields:
            if f.acronym:
                self.acronyms.add(f.acronym)
                for key in of:
                    known = self.fields.setdefault(key, [])
                    if f.acronym not in known:
                        known.append(f.acronym)
            self.add_fields(f.fields, *of)

    def fields_of(self, name: str, dword: Optional[int] = None) -> List[str]:
        """The acronyms of the fields of 'name', of its dword 'dword' where it
        has that dword, in the order of its figures"""

        return self.fields.get((name.lower(), dword)) or self.fields.get(
            (name.lower(), None), []
        )

    def near(self, text: str, query: str = "", most: int = 5) -> List[str]:
        """Up to 'most' names close to 'text', for a question that is not
        known, such as Zone Append for "zone apend". Where 'query' is
        "command", "feature" or "log_page", only names of that kind are
        considered; otherwise every name, acronym and register name is.
        Names that contain 'text' as a whole word come first, then names
        that difflib.get_close_matches() finds. For an identifier, such as
        "ffh", the list is empty."""

        if re.fullmatch(r"[0-9a-f]+h|\d+", text.strip().lower()):
            return []
        kinds = {
            "command": self.commands,
            "feature": self.features,
            "log_page": self.log_pages,
        }
        names = set(kinds.get(query, set()))
        if not names:
            names = self.commands | self.features | self.log_pages
            names |= self.structures | self.acronyms
            for name in self.structures:  # Also a register's name after "CAP - "
                head, dash, rest = name.partition(" - ")
                if dash and head.isupper() and rest:
                    names.add(rest)
        lowered = {name.lower(): name for name in names}
        word = re.compile(rf"(?<!\w){re.escape(text.strip().lower())}(?!\w)")
        holding = sorted(
            (n for n in lowered if word.search(n)), key=lambda n: (len(n), n)
        )
        alike = difflib.get_close_matches(text.lower(), lowered, n=most, cutoff=0.7)
        found = list(dict.fromkeys(holding + alike))[:most]
        return [lowered[name] for name in found]

    @cached_property
    def names(self) -> re.Pattern:
        """A pattern of every name a question may name, the longest first; a
        register also by its name, and no name that is a generic word"""

        names = self.commands | self.features | self.log_pages | self.structures
        for name in self.structures:  # A register also by its name, as spot reads
            head, dash, rest = name.partition(" - ")
            if dash and head.isupper() and rest:
                names.add(rest)
        names = {n for n in names if n.lower() not in GENERIC}
        ordered = sorted(names, key=len, reverse=True)
        if not ordered:
            return re.compile(r"(?!)")  # Matches nothing
        return re.compile(
            r"(?<![\w-])(?:" + "|".join(map(re.escape, ordered)) + r")(?![\w-])",
            re.I,
        )
