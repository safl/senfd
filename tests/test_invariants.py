# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

from senfd.documents.spec import (
    Command,
    CommandSet,
    Dwords,
    Source,
    SpecDocument,
    Structure,
)
from senfd.invariants import violations

BASE = "NVM Express Base Specification, Revision 2-4"


def structure(key: str, figure_nr: int, document: str = BASE) -> Structure:
    return Structure(
        title="Foo",
        name="Foo",
        key=key,
        kind="data_structure",
        unit="bytes",
        source=Source(document=document, figure_nr=figure_nr),
    )


def dwords(lower: int, section: str, document: str = BASE) -> Dwords:
    return Dwords(
        lower=lower,
        upper=lower,
        source=Source(document=document, figure_nr=lower, section=section),
    )


def spec_of(*commands: Command, structures=()) -> SpecDocument:
    spec = SpecDocument()
    spec.structures = list(structures)
    spec.command_sets = {
        "admin": CommandSet(name="Admin", commands={c.name: c for c in commands})
    }
    return spec


def command(*sqe: Dwords) -> Command:
    return Command(
        name="Foo Log",
        opcode=2,
        sqe=list(sqe),
        source=Source(document=BASE, figure_nr=1),
    )


def test_two_structures_of_one_document_with_one_key_are_a_violation():
    """xNVMe names a structure by the key of its document and its own key"""

    spec = spec_of(
        structures=[
            structure("foo", 216),
            structure("foo", 217),
            structure("foo", 5, document="NVM Express NVM Command Set Specification"),
        ]
    )
    assert violations(spec) == [
        "Base 2.4, Figure 217: key 'foo' is also the key of Figure 216"
    ]


def test_dwords_of_a_command_outside_its_section_in_a_document_are_a_violation():
    """The dwords of Get Log Page in Base 2.4 lie in section 5.2.13 and below it; NVM
    1.3 gives the command's dwords in a section of its own"""

    within = command(
        dwords(10, "5.2.13"),
        dwords(11, "5.2.13.1"),
        dwords(12, "3.1.4", document="NVM Express NVM Command Set Specification"),
    )
    assert violations(spec_of(within)) == []
    outside = command(dwords(10, "5.2.13"), dwords(11, "5.2.14"))
    assert violations(spec_of(outside)) == [
        "Base 2.4, 5.2.14, Figure 11: dwords of Foo Log outside section 5.2.13"
    ]
