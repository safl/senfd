# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""What the data model names, which a question may name: the names of its
commands, features, log pages and structures, and the acronyms of their
fields, by the thing and the dword they are of"""

import re
from dataclasses import dataclass, field
from functools import cached_property
from typing import Dict, Iterable, List, Optional, Set, Tuple

from senfd.sate.phrasing import GENERIC
from senfd.documents.spec import Bits, Dwords, SpecDocument

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
