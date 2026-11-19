# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
What holds of every data model senfd makes, whatever documents it is made from

A consumer relies on these: a structure is found by the key of its document and
its own key, and the dwords that one document gives a command or a feature are
those of one section of that document. A check of the public documents runs
violations() on each data model it makes.
"""

from typing import Dict, Iterator, List, Optional, Tuple

from senfd.documents.spec import Dwords, SpecDocument, cite


def keys_unique(spec: SpecDocument) -> Iterator[str]:
    """Each key that two structures of one document have"""

    seen: Dict[Tuple[str, str], int] = {}
    for structure in spec.structures:
        at = (structure.source.document, structure.key)
        if at in seen:
            yield (
                f"{cite(structure.source)}: key '{structure.key}' is also the key "
                f"of Figure {seen[at]}"
            )
        else:
            seen[at] = structure.source.figure_nr


def under(section: Optional[str], top: Optional[str]) -> bool:
    """Whether 'section' is the section 'top' or a section below it"""

    if section is None or top is None:
        return False
    return section == top or section.startswith(f"{top}.")


def one_section(name: str, dwords: List[Dwords]) -> Iterator[str]:
    """For each document giving 'dwords', the dwords of 'name' outside the section of
    the fewest levels among them, which should hold the others"""

    by: Dict[str, List[Dwords]] = {}
    for each in dwords:
        by.setdefault(each.source.document, []).append(each)
    for given in by.values():
        # Of sections equally deep, the one of the dwords given first
        sections = [d.source.section for d in given]
        top = min(sections, key=lambda s: (s or "").count("."))
        for each in given:
            if not under(each.source.section, top):
                yield f"{cite(each.source)}: dwords of {name} outside section {top}"


def violations(spec: SpecDocument) -> List[str]:
    """What of 'spec' does not hold that should, each as a sentence"""

    found = list(keys_unique(spec))
    for command_set in spec.command_sets.values():
        for command in command_set.commands.values():
            found += one_section(command.name, command.sqe + command.cqe)
    for feature in spec.features.values():
        found += one_section(feature.name, feature.sqe + feature.cqe)
    return found
