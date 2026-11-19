# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
The specification document: the model of a specification made from its
normalised figures, for generating code from and for answering questions with

Everything in it says where it came from, the document and the figure, so an
answer can be checked against the specification. What a figure holds that the
model leaves out is a diagnostic.
"""

import re
from argparse import Namespace
from pathlib import Path
from typing import ClassVar, Dict, Iterator, List, Literal, Optional, Tuple, Union

from pydantic import ConfigDict, Field, model_validator
from pydantic.config import JsonDict

from senfd.documents.base import (
    DocumentMeta,
    Converter,
    Document,
    Model,
    strip_all_suffixes,
)
from senfd.documents.normalized import (
    Layout,
    LayoutField,
    NormalizedFigure,
    NormalizedFigureDocument,
)
from senfd.errors import Error
from senfd.fields import Role
from senfd.normalize import (
    CaptionKind,
    Diagnostic,
    is_long_name,
    normalize_text,
    note,
    warning,
)
from senfd.ranges import RangeKind, Unit
from senfd.utils import key_of, unmarked
import senfd.fields
import senfd.identity
import senfd.ranges


class Source(Model):
    """Where something came from: the document, the figure, the page the
    figure is on, and the section it is in, by number and title"""

    document: str
    """The document, by the name of its file, as 'NVM Express Base
    Specification, Revision 2-4 Ratified 2026-08-21'"""
    figure_nr: int
    """The number of the figure"""
    page_nr: Optional[int] = None
    """The page the figure is on, by the document's table of figures"""
    pdf_page: Optional[int] = None
    """The page the figure is on in the PDF, counted from the file's first
    page, where the document was read from a PDF; a link opens it there"""
    section: Optional[str] = None
    """The number of the section the figure is in, as '3.1.4.1'"""
    section_title: Optional[str] = None
    """The title of that section"""


# What a field's JSON must hold for each kind of range, as a JSON Schema can
# say it; what its values must be besides is Bits.of_its_kind's to say
BITS_BY_KIND: JsonDict = {
    "allOf": [
        {
            "if": {"properties": {"kind": {"const": "span"}}},
            "then": {
                "properties": {
                    "upper": {"type": "integer", "minimum": 0},
                    "lower": {"type": "integer", "minimum": 0},
                    "formula": {"type": "null"},
                    "width": {"type": "integer", "minimum": 1},
                },
                "required": ["upper", "lower", "width"],
            },
        },
        {
            "if": {"properties": {"kind": {"const": "formula"}}},
            "then": {
                "properties": {
                    "upper": {"type": "null"},
                    "lower": {"type": "null"},
                    "formula": {
                        "type": "string",
                        "pattern": r"^[-A-Za-z0-9_ .*+\u2026]+:[-A-Za-z0-9_ .*+\u2026]+$",
                    },
                },
                "required": ["formula"],
            },
        },
        {
            "if": {"properties": {"kind": {"const": "open"}}},
            "then": {
                "properties": {
                    "upper": {"type": "null"},
                    "lower": {"type": "null"},
                    "formula": {"type": "null"},
                    "width": {"type": "null"},
                }
            },
        },
    ]
}


class Placement(Model):
    """Where a field is while a condition heading the figure's columns of
    ranges holds. For example, the PDU Header Digest of the TCP transport's
    Command Capsule PDU is bytes 75:72 when HDGSTF=1 and not present when
    HDGSTF=0."""

    condition: str
    """The condition as the figure writes it, for example 'HDGSTF=1'"""
    range: Optional[str] = None
    """The range under the condition as the figure writes it; None where the
    figure says the field is not present"""
    upper: Optional[int] = None
    """The upper bound of the range, inclusive; None where it is symbolic"""
    lower: Optional[int] = None
    """The lower bound of the range"""


class BitsCommon(Model):
    """What a field has however far it is made"""

    name: Optional[str] = None
    """The name of the field, as 'Force Unit Access'"""
    acronym: Optional[str] = None
    """Its acronym, as "FUA"; None where it has none or the document's is not
    one, which is then an erratum"""
    upper: Optional[int] = None
    """The upper bound of the range, inclusive"""
    lower: Optional[int] = None
    """The lower bound of the range"""
    range: str
    """The range as the document writes it, as "29:26" or '03:00'"""
    description: str = ""
    """The text of the field's description"""
    section: Optional[str] = None
    """The heading of a row of the figure that groups fields, as the fields
    under it are of"""
    elided: bool = False
    """Whether the figure leaves rows out before it, as "..." between the
    first and the last of entries counted by a value"""
    columns: Dict[str, str] = Field(default_factory=dict)
    """The figure's other columns of the field, by their keys, as "reset" or
    'type'"""
    union: Optional[int] = None
    """Of fields sharing bits, the union of the layout they are of"""
    alternative: Optional[int] = None
    """Of fields sharing bits, which fields go together, as an IPv4 address
    and the reserved bits after it, against an IPv6 address of the same
    bytes"""
    placements: List[Placement] = Field(default_factory=list)
    """The range of the field under each condition heading the figure's
    columns of ranges, where those differ; 'range' is the first that is
    present"""
    byte_order: Optional[Literal["big-endian", "little-endian"]] = None
    """
    The order of the bytes of the field where the figure marks the byte of its most
    significant bit (MSB) and the byte of its least significant bit (LSB), as the
    protection information formats of the NVM Command Set do: "big-endian" where the MSB
    is in the lowest byte. Otherwise the byte order that the description states, for
    example "This field is big endian" of FGUID of Identify Controller. None where
    neither gives one, and for a field of one byte.
    """
    encoding: Optional[Literal["ascii", "utf-8", "uuid"]] = None
    """
    What the bytes of the field encode, where the description says: "ascii" for "as an
    ASCII string", "utf-8" for "a UTF-8 null-terminated string", and "uuid" for "a
    128-bit Universally Unique Identifier (UUID)". Otherwise the encoding taken from
    another field, for example from the field that FR of NVM 1.3 Figure 189 has the
    value of, "the value of the FR field in the Identify Controller data structure".
    """
    encoding_from: Optional[Source] = None
    """
    The figure of the field that 'encoding' is taken from, where the description of this
    field does not state the encoding. For example, AVENQN of Base 2.4 Figure 328, an
    NQN, takes "utf-8" from SUBNQN of Figure 338. None where the encoding is stated.
    """
    byte_order_from: Optional[Source] = None
    """
    The figure of the field that 'byte_order' is taken from, a field of the same name,
    acronym and width in another document, where this field does not state the byte
    order. For example, NGUID of KV 1.4 Figure 42 takes it from NVM 1.3 Figure 123. None
    where the byte order is stated.
    """
    footnotes: List[int] = Field(default_factory=list)
    """The numbers of the footnotes marked on the name, at the end of the
    description, and on the other columns"""
    values: List["Entry"] = Field(default_factory=list)
    """The values the field takes, as the table in its description gives
    them"""


class Selected(Model):
    """A value of the controlling field that a case applies to"""

    name: str
    """The name of the value as the figure writes it, for example 'Report
    Zones'"""
    value: Optional[int] = None
    """The value as a number, for example 0 for 00h; None where the
    controlling field has no value of that name"""


class CaseCommon(Model):
    """The parts that a parsed case and a checked case share"""

    selector: str
    """The controlling field: its acronym where the figure has a field of
    the name that heads the table of cases, for example "ZRA" for 'Zone
    Receive Action', and otherwise that name"""
    when: List[Selected] = Field(default_factory=list)
    """The values of the controlling field that the case applies to; empty
    for the case of all other values"""
    otherwise: bool = False
    """Whether the case applies to every value of the controlling field that
    no other case lists, as the row 'All other values' says"""
    name: Optional[str] = None
    """The name of the field in this case, for example "Reporting Options" or
    "Reserved"; None where the figure gives no name"""
    acronym: Optional[str] = None
    """The acronym of the field in this case, for example 'ZRWAA'"""
    description: str = ""
    """The description of the field in this case"""
    values: List["Entry"] = Field(default_factory=list)
    """The values of the field in this case"""


class ReadCase(CaseCommon):
    """A case as parsed from the figure, which checked() turns into a Case"""

    fields: List["ReadBits"] = Field(default_factory=list)
    """The rows that lay out the field in this case"""


class ReadBits(BitsCommon):
    """A row of a layout as read, from which checked() makes a field or not"""

    unit: Unit
    """What the range counts: "bits" or 'bytes'"""
    fields: List["ReadBits"] = Field(default_factory=list)
    """The rows within this one, as its description lays them out"""
    cases: List[ReadCase] = Field(default_factory=list)
    """The cases of the row, where its meaning depends on the value of
    another field"""


class Part(Model):
    """
    The value of which a field holds a part, where a figure splits the value over two
    fields. Examples are NUMDL and NUMDU of Get Log Page, "Number of Dwords Lower" and
    "Upper", and "KV Key[63:00]" and "KV Key[127:64]" of KV 1.4.
    """

    name: str
    """The name of the value, for example 'Number of Dwords'"""
    acronym: Optional[str] = None
    """
    The acronym of the value, for example 'NUMD', where the acronym of each part is this
    acronym and a letter for the part
    """
    shift: int
    """
    The bit of the value where the field starts, in the unit of the range of the field:
    0 for the lower part, and the width of the lower part for the upper part, for
    example 64 for "KV Key[127:64]"
    """


class Array(Model):
    """
    The array that a field belongs to. A figure lists the entries of an array
    as fields numbered by their index and replaces the rows between them with
    "...", for example LBAF0, LBAF1, "..." and LBAF63 of Identify Namespace.
    Each listed entry has the array, with its own index.
    """

    name: str
    """The name of the entries without the index, for example 'LBA Format
    Support'"""
    acronym: Optional[str] = None
    """The acronym of the entries without the index, for example 'LBAF'"""
    index: Optional[int] = None
    """
    The index of this entry, for example 63 for LBAF63, or 255 for "Performance
    Attribute FFh Identifier". None for a last entry whose range the figure gives as a
    formula.
    """
    first: int
    """The index of the first entry, 0 or 1 depending on the figure"""
    count: Optional[int] = None
    """The number of entries, for example 64; None where the figure gives the
    range of the last entry as a formula, because the number is then a value
    in the data"""
    stride: Optional[int] = None
    """
    The size of one entry, in the unit of the field. None where the data gives the size
    of each entry, for example the ANA Group Descriptors of Base 2.4 Figure 230 at
    "n:16" and "m:n+1".
    """
    lower: Optional[int] = None
    """
    The offset of the first entry, where the array starts. None where the data gives it.
    """
    maximum: Optional[int] = None
    """The most entries the array holds, where it has no count and a
    paragraph referring to its figure states it, as "up to 511 Zone
    Identifier entries" of the Changed Zone List of ZNS 1.5"""
    counted_by: Optional[str] = None
    """
    The acronym of the field of the structure that holds the number of entries, where
    the array has no count and the last entry names that field, as NZID of "Zone
    Identifier NZID-1" of the Changed Zone List of ZNS 1.5, or NUMENT of "SC Entry
    NUMENT-1" of the Secondary Controller List of Base 2.4
    """


class Case(CaseCommon):
    """
    The meaning of a field while another field of its figure has certain
    values. For example, bits 15:08 of Zone Management Receive, ZRAS, are the
    Reporting Options when ZRA is Report Zones or Extended Report Zones, and
    are reserved for all other values of ZRA.
    """

    role: Role = "field"
    """The role of the field in this case: a "field", or a placeholder such
    as 'reserved'"""
    fields: List["Bits"] = Field(default_factory=list)
    """The subfields of the field in this case"""
    selector_in: Optional[Source] = None
    """The figure of the controlling field where it is a field of another
    figure, as Base 2.4 Figure 92, Command Dword 0, for PSDT of DPTR, whose
    description names it "CDW0.PSDT": the structure that the field of the
    case's figure named before the dot links to"""


class Bits(BitsCommon):
    """
    A field of bits or bytes, made with what it needs; 'upper' and 'lower'
    are None where the document gives the range by a formula, or leaves it
    open, as 'kind' says
    """

    model_config = ConfigDict(
        use_attribute_docstrings=True, json_schema_extra=BITS_BY_KIND
    )

    name: str
    """The name of the field, as 'Force Unit Access', or of the place it
    holds, as 'Reserved'"""
    unit: Unit
    """What the range counts: "bits" or 'bytes'"""
    role: Role
    """What the field is: a "field" of its name, or what holds a place,
    "reserved", "obsolete", "vendor_specific" or 'ignored'"""
    kind: RangeKind
    """What the range is: a "span" of numbers, a "formula" of values the
    figure names, as "(N*16)+15:N*16", or "open", as 'n/a' or 'Impl Spec'"""
    formula: Optional[str] = None
    """Of a formula, its bounds written plainly, "upper:lower", as
    '16*N + 15:16*N'"""
    width: Optional[int] = None
    """How many bits or bytes the range is, where its bounds give it, as 16
    of '16*N + 15:16*N'"""
    fields: List["Bits"] = Field(default_factory=list)
    """The fields within this one, as its description lays them out"""
    values_in: Optional[Source] = None
    """The source of the table of values of the field, where the description
    of the field refers to that figure instead of listing the values, for
    example "Refer to Figure 336". The table is the entry of the data model's
    'values' with this source."""
    cases: List[Case] = Field(default_factory=list)
    """The cases of the field, where a table in its description gives the
    meaning of the field for each value of another field of its figure"""
    array: Optional[Array] = None
    """The array that the field belongs to, where the figure lists numbered
    entries and leaves out the rows between them"""
    part: Optional[Part] = None
    """
    The value that the field holds a part of, where a figure splits a value over two
    fields
    """
    structure: Optional[Source] = None
    """The source of the structure that lays out the field. The description of
    the field refers to the figure, for example "defined in Figure 125", or,
    for an entry of an array, names the structure, for example "an I/O
    Command Set Vector". The structure is the entry of the data model's
    'structures' with this source."""

    @model_validator(mode="after")
    def of_its_kind(self) -> "Bits":
        """A span has its bounds, the upper not below the lower, and its
        width by them; a formula its text and no bounds; an open range none"""

        bounds = (self.upper, self.lower)
        if self.kind == "span":
            if self.upper is None or self.lower is None:
                raise ValueError(f"The span '{self.range}' has no bounds")
            if self.upper < self.lower or self.formula is not None:
                raise ValueError(f"'{self.range}' is no span")
            if self.width != self.upper - self.lower + 1:
                raise ValueError(f"'{self.range}' is not {self.width} wide")
        elif bounds != (None, None) or (self.formula is None) != (self.kind == "open"):
            raise ValueError(f"'{self.range}' is no {self.kind} range")
        return self


class Comparison(Model):
    """
    A condition on the value of a field, for example "CETYPE is non-zero"
    """

    field: str
    """The acronym of the field, for example 'CETYPE'"""
    comparison: Literal["==", "!="]
    """How the value of the field compares with 'value'"""
    value: int
    """The value that the field is compared with"""


REGEX_COMPARISON = re.compile(
    r"^(?P<field>[A-Z][A-Z0-9]*) is (?:(?:cleared|set) to (?P<value>[0-9A-F]+h|[01]+b|\d+)"
    r"|(?P<nonzero>non-zero))$"
)


def comparison_of(condition: Optional[str]) -> Optional[Comparison]:
    """
    The comparison that 'condition' states, for example CETYPE == 0 for "CETYPE is
    cleared to 0h". Returns None for a condition of another form.
    """

    match = REGEX_COMPARISON.match(condition or "")
    if not match:
        return None
    if match["nonzero"]:
        return Comparison(field=match["field"], comparison="!=", value=0)
    return Comparison(
        field=match["field"], comparison="==", value=code_value(match["value"])
    )


class Dwords(Model):
    """The dwords 'lower' to 'upper' of a command, and their fields"""

    lower: int
    """The first dword, as 10 of CDW10"""
    upper: int
    """The last dword, the same as 'lower' for one dword"""
    condition: Optional[str] = None
    """Where the figure lays the dwords out only under a condition, the
    condition, as 'CETYPE is cleared to 0h'"""
    selected_when: Optional[Comparison] = None
    """
    The condition as a comparison of a field with a value, where the condition has the
    form "X is cleared to 0h", "X is set to 1h" or "X is non-zero"
    """
    qualifier: Optional[str] = None
    """What the caption says the dwords are of, as 'NVM Command Set Specific
    Fields'"""
    refines: Optional[str] = None
    """
    The acronym of the field of the dwords of the command whose bits these dwords lay
    out, where all the fields of these dwords lie within that one field. Examples are
    LSP of Get Log Page Command Dword 10, for the FDP Events of Base 2.4 Figure 301, and
    CNSSID of Identify Command Dword 11.
    """
    fields: List[Bits] = Field(default_factory=list)
    """The fields of the dwords, the bits counted across them"""
    source: Source
    """The figure laying them out"""


class Operation(Model):
    """
    What a command does for the values of its selecting fields, as a directive
    operation of Directive Receive by its directive type (DTYPE) and operation
    (DOPER), with the dwords and the structures of that operation
    """

    name: str
    """The name of the operation"""
    selectors: Dict[str, int] = Field(default_factory=dict)
    """The values of the command's fields selecting it, by acronym, as
    {"DTYPE": 0, "DOPER": 1}"""
    sqe: List[Dwords] = Field(default_factory=list)
    """The submission queue entry dwords of the operation"""
    cqe: List[Dwords] = Field(default_factory=list)
    """The completion queue entry dwords of the operation"""
    structures: List[str] = Field(default_factory=list)
    """The keys of the structures the operation transfers, structures of the
    document of 'source'"""
    source: Source
    """The figure listing the operation"""


class ValueLink(Model):
    """
    A value of a field of another figure that an entry's description names.
    For example, Reporting Options 1h of Zone Management Receive, "List the
    zones in the ZSE:Empty state.", names the zone state ZSE:Empty, which is
    value 1h of the field ZS of the Zone Descriptor, ZNS 1.5 Figure 38.
    """

    source: Source
    """The figure of the field"""
    field: str
    """The field by its acronym, or by its name where it has none, as 'ZS'"""
    value: str
    """The value as the figure writes it, as '1h'"""
    acronym: Optional[str] = None
    """The acronym the description gives the value, as 'ZSE'"""


class Command(Model):
    """A command, by its opcode, with its dwords and its operations"""

    name: str
    """The name of the command, as 'Write'"""
    opcode: int
    """The opcode"""
    sqe: List[Dwords] = Field(default_factory=list)
    """The dwords of its submission queue entry that its figures lay out"""
    cqe: List[Dwords] = Field(default_factory=list)
    """The dwords of its completion queue entry that its figures lay out"""
    operations: List[Operation] = Field(default_factory=list)
    """What it does for the values of its selecting fields, if it has any"""
    status_values: List[Source] = Field(default_factory=list)
    """The tables of the status values specific to the command, as Base 2.4
    Figure 331 of Get Log Page"""
    status_codes: List[ValueLink] = Field(default_factory=list)
    """The status values whose "Commands Affected" names the command, as
    00h, Completion Queue Invalid, of Base 2.4 Figure 104 for Create I/O
    Submission Queue"""
    columns: Dict[str, str] = Field(default_factory=dict)
    """The opcode table's other columns of the command, by their keys"""
    footnotes: Dict[str, List[int]] = Field(default_factory=dict)
    """
    The numbers of the footnotes marked on the name and the other columns of the row of
    the command, by the key of the column, where a footnote is marked
    """
    source: Source
    """The opcode table listing the command"""


CommandSetKind = Literal["admin", "io", "common_io", "management_interface", "other"]


class CommandSet(Model):
    """The commands of an opcode table, as Admin or NVM"""

    name: str
    """The name of the command set"""
    kind: CommandSetKind = "other"
    """
    The kind of the command set. "io" is an I/O command set, which an I/O Command Set
    specification defines. "common_io" is the I/O commands that the Base specification
    defines for use in all I/O command sets; these commands are not a command set and
    have no Command Set Identifier. "admin" is the Admin command set, and
    "management_interface" is a command set of the Management Interface specification.
    """
    identifier: Optional[int] = None
    """
    The Command Set Identifier (CSI) of an I/O command set, as Base 2.4 Figure 337 gives
    it, for example 00h for NVM. None for the other kinds, and where the table of
    identifiers is not among the documents.
    """
    commands: Dict[str, Command] = Field(default_factory=dict)
    """Its commands, by their names as keys, as 'zone_append'"""


class Structure(Model):
    """
    A layout of fields that is no command's dwords: a data structure, a log
    page, a register or anything else a figure lays out
    """

    title: str
    """The name its caption gives, as 'CC - Controller Configuration'"""
    name: str
    """
    The name of the structure without the parts of its title that 'owner', 'acronym',
    'optional', 'qualifier' and the offset hold, as "Controller Configuration" of "CC -
    Controller Configuration" and "Identify Controller" of "Identify - Identify
    Controller"
    """
    owner: Optional[str] = None
    """
    What the title names before " - " where that is no acronym: the command, feature,
    log page or structure the structure is of, as "Identify" of "Identify - Identify
    Controller"
    """
    acronym: Optional[str] = None
    """
    The acronym of the structure, as "CC" of "CC - Controller Configuration",
    "PXDCAP2" of "Offset PXCAP + 24h: PXDCAP2 - PCI Express Device Capabilities 2" and
    "CH" of 'PDU Common Header (CH)'
    """
    optional: bool = False
    """Whether the title marks the structure "(Optional)", as BIST of PCIe 1.4"""
    key: str = ""
    """
    The key of the structure, unique among the structures of its document. It is the
    key of the name without words that the document and the context give: "Data
    Structure", the name of the document's command set, and "I/O Command Set
    Specific" and the like, as "identify_namespace" of NVM 1.3 Figure 123. Where two
    structures of a document would have the same key, the key of each includes those
    words, then its owner, its qualifier, its kind and, last, its figure number, as far
    as it takes to tell them apart, as "timestamp_set_features" and
    'timestamp_get_features'.
    """
    kind: CaptionKind
    """What its caption says it is, as "data_structure", "log_page" or
    "register", or 'other'"""
    unit: Unit
    """What its fields' ranges count: "bits" or 'bytes'"""
    qualifier: Optional[str] = None
    """
    What the caption says it is of, as "Log Specific Field", or what its title gives
    in parentheses that is no acronym, as "Set Features" of "Timestamp (Set Features)"
    or "Event Type 02h"
    """
    offset: Optional[int] = None
    """
    Of a register, its offset in bytes, as 20 of CC at 14h; of a register of a
    capability, its offset from 'offset_base', as 2 of 'Offset PMCAP + 2h'
    """
    offset_base: Optional[str] = None
    """
    The register of the capability that 'offset' counts from, as "PMCAP" of 'Offset
    PMCAP + 2h'
    """
    offset_formula: Optional[str] = None
    """
    The offset where the title gives it by a formula, as the doorbell registers of
    PCIe 1.4 at '(1000h + ((2y) * (4 << CAP.DSTRD)))'
    """
    size: Optional[int] = None
    """
    The size of the structure in bytes, by the highest bound of its fields. None where
    a field's range is a formula or open, so that the data gives the size.
    """

    @model_validator(mode="before")
    @classmethod
    def titled(cls, data):
        """A structure made with a name and no title has its name as its title"""

        if isinstance(data, dict) and "title" not in data and "name" in data:
            data = {**data, "title": data["name"]}
        return data
    fields: List[Bits] = Field(default_factory=list)
    """Its fields"""
    notes: List[str] = Field(default_factory=list)
    """The notes of the figure"""
    source: Source
    """The figure laying it out"""
    extends: Optional[Source] = None
    """
    The figure of the structure of which this structure lays out some of the bytes. For
    example, NVM 1.3 Figure 126, with AWUN, AWUPF and ACWU, extends Identify Controller,
    Base 2.4 Figure 338.
    """
    extends_field: Optional[str] = None
    """
    The acronym of the field of the extended structure that this structure lays out,
    where the text names it, for example CPSR of MI 2.2 Figure 40 for Figure 41
    """


TypedKind = Literal[
    "level",
    "flag",
    "identifier",
    "identifiers",
    "number",
    "others",
    "note",
    "reference",
    "reserved",
    "vendor_specific",
    "not_applicable",
]
# What each kind of typed value must hold, as a JSON Schema can say it
TYPED_BY_KIND: JsonDict = {
    "allOf": [
        {
            "if": {"properties": {"kind": {"enum": [*kinds]}}},
            "then": {"properties": {name: {"type": of}}, "required": [name]},
        }
        for kinds, name, of in (
            (["level"], "level", "string"),
            (["flag"], "flag", "boolean"),
            (["identifier", "number"], "lower", "integer"),
            (["identifiers"], "listed", "array"),
            (["note"], "note", "integer"),
            (["reference"], "reference", "string"),
        )
    ]
}


class Typed(Model):
    """
    A value of a table as what it is: a requirement "level" (M, O, P, NR, R),
    a yes or no "flag", an "identifier" or a range of them, "identifiers" listed, a
    "number" or a range of them, "others" for the row of all other values, a "note"
    it is given by, a "reference" to another specification, or "reserved",
    "vendor_specific" or "not_applicable"; with the footnotes marked on it
    """

    model_config = ConfigDict(
        use_attribute_docstrings=True, json_schema_extra=TYPED_BY_KIND
    )

    kind: TypedKind
    """Which of those it is"""
    level: Optional[str] = None
    """Of a level, the level"""
    flag: Optional[bool] = None
    """Of a flag, whether yes"""
    lower: Optional[int] = None
    """Of an identifier, it, or the first of a range"""
    upper: Optional[int] = None
    """Of a range of identifiers or numbers, the last"""
    listed: List[int] = Field(default_factory=list)
    """Of identifiers listed, as '00h, 01h, 08h, and 09h', each of them"""
    note: Optional[int] = None
    """Of a note, its number"""
    reference: Optional[str] = None
    """Of a reference, the specification referred to"""
    footnotes: List[int] = Field(default_factory=list)
    """The numbers of the footnotes marked on the value"""


class Entry(Model):
    """A row of a table of values, as a status value or a log page identifier;
    'typed' has the values of its columns of a known kind as what they are"""

    value: str
    """The value, as the document writes it, as '1Fh'"""
    value_column: str = ""
    """The key of the column holding the value"""
    name: Optional[str] = None
    """The name the row gives the value"""
    acronym: Optional[str] = None
    """
    The acronym of the value. The row can write it before the name, for example "CAP" of
    "CAP: Controller Capabilities" in Base 2.4 Figure 33, or as the initials after the
    name, for example "GAZ" of "Get Active ZoneGroup (GAZ) operation". The table can
    also give it in an Acronym column.
    """
    description: str = ""
    """The text of the row's description"""
    columns: Dict[str, str] = Field(default_factory=dict)
    """The row's other columns, by their keys"""
    typed: Dict[str, Typed] = Field(default_factory=dict)
    """
    The values of the row's columns of a known kind, by their keys. The value of every
    row whose value is a code, a range of codes or a number is typed, under the key
    'value_column'.
    """
    role: Role = "field"
    """
    What the row is: "field" for a value of its own meaning, or the place a value holds,
    "reserved", "obsolete", "vendor_specific" or "ignored", as the row of "4h to 6h"
    named "Reserved" in Base 2.4 Figure 102
    """
    footnotes: List[int] = Field(default_factory=list)
    """The numbers of the footnotes marked on the row: on the value, the
    name, the description and the other columns, in that order"""
    marked: Dict[str, List[int]] = Field(default_factory=dict)
    """
    The numbers of the footnotes marked on each column, by the key of the column, with
    the key "name" for the name, where a footnote is marked
    """
    refers_to: Optional[ValueLink] = None
    """The value of another field that the description names, where the entry
    has no name of its own"""
    selects: List[Source] = Field(default_factory=list)
    """The structures the value selects, as the Identify Controller data
    structure and its Power State Descriptor for CNS 01h: those of the
    section its reference cites, those of the same value in a document it
    cites, or, where the Command Set Identifier selects them, those of the
    same value in each command set's document"""
    document: Optional[str] = None
    """The document whose subject the entry names, as the NVM Command Set
    Specification for "NVM Command Set" of the Command Set Identifiers"""


StatusScope = Literal["io_command_set", "fabrics"]

# The Status Code Type of a table of status values by the words of its caption, as
# Base 2.4 Figure 102 gives them
STATUS_CODE_TYPES = {
    "generic_command": 0,
    "command_specific": 1,
    "command_operation_specific": 1,
    "media_and_data_integrity_error": 2,
    "path_related": 3,
}
STATUS_SCOPES: Dict[str, StatusScope] = {
    "io_command_set_specific": "io_command_set",
    "fabrics_command_specific": "fabrics",
}


class Values(Model):
    """A table of values, by the kind of its caption and what it names; the
    scope is what the caption confines it to, as "I/O Commands" """

    kind: CaptionKind
    """What its caption says it is, as "status_values", "requirements" or
    "log_page_identifiers", or 'other'"""
    name: Optional[str] = None
    """What the caption names, as the command or field the values are of"""
    qualifier: Optional[str] = None
    """What else the caption says they are of"""
    scope: Optional[str] = None
    """What the caption confines them to, as 'I/O Commands'"""
    columns: List[str] = Field(default_factory=list)
    """The keys of its columns"""
    entries: List[Entry] = Field(default_factory=list)
    """Its rows"""
    status_code_type: Optional[int] = None
    """
    The Status Code Type of the status codes of a table of status values, by its
    caption, as 1 of "Command Specific Status Values" and 2 of "Media and Data
    Integrity Error Values"
    """
    status_scope: Optional[StatusScope] = None
    """
    What the caption of a table of status values confines its codes to, beyond the
    document: "io_command_set" of "Status Code - Command Specific Status Values, I/O
    Command Set Specific", or "fabrics" of the Fabrics Command Specific ones
    """
    source: Source
    """The figure holding the table"""


class Feature(Model):
    """A feature, by its identifier, and the dwords of the commands setting and
    getting it that are described for it"""

    identifier: int
    """The feature identifier, as 7 of 07h"""
    name: str
    """The name of the feature, as 'Number of Queues'"""
    columns: Dict[str, str] = Field(default_factory=dict)
    """The feature identifier table's other columns of it, by their keys, as
    its requirements"""
    footnotes: Dict[str, List[int]] = Field(default_factory=dict)
    """
    The numbers of the footnotes marked on the name and the other columns of the row of
    the feature, by the key of the column, where a footnote is marked
    """
    sqe: List[Dwords] = Field(default_factory=list)
    """The submission queue entry dwords described for it"""
    cqe: List[Dwords] = Field(default_factory=list)
    """The completion queue entry dwords described for it"""
    operations: List["Operation"] = Field(default_factory=list)
    """
    What the feature does for each value of a field of its dwords, for example the
    Lockdown Persistence Personality of Configurable Device Personality, selected by
    PERID 02h
    """
    source: Source
    """The feature identifier table listing it"""


class LogPage(Model):
    """A log page, by its identifier, and the structure laying it out"""

    identifier: int
    """The log page identifier, as 2 of 02h"""
    name: str
    """The name of the log page, as 'SMART / Health Information'"""
    aliases: List[str] = Field(default_factory=list)
    """
    The other names that the tables give the log page, for example "Manufacturer Default
    Configuration Status" of Base 2.4 Figure 31 for 24h, which Figure 209 names
    "Manufacturer Default Configuration"
    """
    columns: Dict[str, str] = Field(default_factory=dict)
    """The log page identifier table's other columns of it, by their keys"""
    footnotes: Dict[str, List[int]] = Field(default_factory=dict)
    """
    The numbers of the footnotes marked on the name and the other columns of the row of
    the log page, by the key of the column, where a footnote is marked
    """
    structure: Optional[Structure] = None
    """The structure laying it out, where a figure is known for it"""
    source: Source
    """The log page identifier table listing it"""


ErratumCode = Literal[
    "value",
    "acronym",
    "range",
    "range-outside",
    "range-reversed",
    "opcode",
    "gap",
    "layout-gap",
    "reference",
    "caption",
]


class Erratum(Model):
    """
    Something of a figure that is not what its kind of value must be, as a
    range beyond the dword it is of, left out of the model; or fields that do
    not fit together, as two of the same bits, which the model keeps. Each is
    a candidate erratum of the specification, saying where it is.
    """

    code: ErratumCode
    """
    The kind of erratum: "value", "acronym", "range" (text that is not a range),
    "range-outside", "range-reversed", "opcode", "gap" (in the dwords of a command),
    "layout-gap" (in a structure), "reference" (to the section of another value) or
    "caption" (of another figure)
    """
    message: str
    """What is wrong, said for a person"""
    found: str = ""
    """The text found in the figure"""
    source: Source
    """The figure it is in"""


class SpecDocument(Document):
    """The data model of the specification, of one document or, merged, of
    several"""

    SUFFIX_JSON: ClassVar[str] = ".spec.document.json"
    SUFFIX_HTML: ClassVar[str] = ".spec.document.html"

    FILENAME_SCHEMA: ClassVar[str] = "spec.document.schema.json"
    FILENAME_HTML_TEMPLATE: ClassVar[str] = "spec.document.html.jinja2"

    command_sets: Dict[str, CommandSet] = Field(default_factory=dict)
    """The command sets of the opcode tables, by their names as keys"""
    dwords: Dict[str, List[Dwords]] = Field(default_factory=dict)
    """The dwords of every figure, by the name its caption gives, as read"""
    structures: List[Structure] = Field(default_factory=list)
    """Every layout that is no command's dwords"""
    values: List[Values] = Field(default_factory=list)
    """The tables of values"""
    features: Dict[str, Feature] = Field(default_factory=dict)
    """The features, by their names as keys"""
    log_pages: Dict[str, LogPage] = Field(default_factory=dict)
    """The log pages, by their names as keys"""
    unassigned: Dict[str, List[Dwords]] = Field(default_factory=dict)
    """The dwords no command, feature or operation claims, by the name their
    caption gives"""
    diagnostics: List[Diagnostic] = Field(default_factory=list)
    """What senfd normalised, or could not read as data"""
    errata: List[Erratum] = Field(default_factory=list)
    """The candidate errata of the documents"""
    sections: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    """The title of each numbered section, by its number as printed, of each
    document by its name"""
    documents: Dict[str, DocumentMeta] = Field(default_factory=dict)
    """The documents the data model is of, by name, each with the file it
    was made from and the file's SHA-256, by which a published one is known"""


REGEX_DOCUMENT = re.compile(
    r"NVM Express (?P<name>.+?) Specification,? Revision (?P<revision>[\d\-.]+)"
)

# The keys of the specifications, by their short names. A specification not listed
# here is keyed by key_of() its short name.
DOCUMENT_KEYS = {
    "Base": "base",
    "Boot": "boot",
    "Computational Programs": "cp",
    "Key Value": "kv",
    "Management Interface": "mi",
    "NVM": "nvm",
    "NVMe over PCIe Transport": "pcie",
    "NVMe over RDMA Transport": "rdma",
    "NVMe over TCP Transport": "tcp",
    "Subsystem Local Memory": "slm",
    "Zoned Namespace": "zns",
}


def document_parts(document: str) -> Optional[Tuple[str, str]]:
    """
    The name and the revision of the specification 'document', for example
    ("NVM Command Set", "1.3"); None for a document of another name
    """

    match = REGEX_DOCUMENT.match(document)
    if not match:
        return None
    return match["name"], match["revision"].replace("-", ".")


def document_key(document: str) -> Optional[str]:
    """The key of the specification 'document' without its revision, as 'nvm'"""

    parts = document_parts(document)
    if parts is None:
        return None
    short = re.sub(r" Command Set$", "", parts[0])
    return DOCUMENT_KEYS.get(short, key_of(short))


def document_name(document: str) -> str:
    """A document by a short name, as "Base 2.2" """

    parts = document_parts(document)
    if parts is None:
        return document
    return f"{re.sub(r' Command Set$', '', parts[0])} {parts[1]}"


def cite(source: Source) -> str:
    """Where 'source' is, as "Base 2.2, 5.1.10, Figure 190, page 195", and
    where it was read from a PDF, the page of the file too, as "page 195,
    PDF page 220", which is where a link to the file opens"""

    parts = [document_name(source.document)]
    if source.section:
        parts.append(source.section)
    parts.append(f"Figure {source.figure_nr}")
    if source.page_nr:
        parts.append(f"page {source.page_nr}")
    if source.pdf_page:
        parts.append(f"PDF page {source.pdf_page}")
    return ", ".join(parts)


CITED = re.compile(
    r"\[([^\[\]]+?, (?:[^\[\]]*?, )?Figure \d+(?:, page \d+)?(?:, PDF page (\d+))?)\]"
)


def linked(document: "SpecDocument", lines: List[str]) -> List[str]:
    """'lines' of Markdown with each citation made a link to the published
    PDF of its document, at the page cited, where the document is one NVM
    Express publishes, known by the SHA-256 of the file it was read from"""

    from senfd.published import url_of

    urls = {
        document_name(name): url_of(meta.sha256)
        for name, meta in document.documents.items()
        if meta.sha256
    }
    if not any(urls.values()):
        return list(lines)

    def link(match: "re.Match[str]") -> str:
        cited = match.group(1)
        url = urls.get(cited.split(", ")[0])
        if not url:
            return match.group(0)
        page = match.group(2)
        return f"[{cited}]({url}#page={page})" if page else f"[{cited}]({url})"

    return [CITED.sub(link, line) for line in lines]


def dwords_named(key: str, dwords: "Dwords") -> str:
    """Dwords as an author reads them, by the name their caption gives, as
    "dwords 0:0 of the completion of Abort" of 'cqe:abort_command'"""

    completion = key.startswith("cqe:")
    name = key.removeprefix("cqe:")
    if name.startswith(QUALIFIED):
        name = "the field " + name.removeprefix(QUALIFIED)
    name = re.sub(r" command$", "", name.replace("_", " "))
    of = f"the completion of {name}" if completion else name
    return f"dwords {dwords.lower}:{dwords.upper} of {of}"


def without_footnote(name: str) -> str:
    """'name' without a footnote marker, as "Flush4" or "Cancel 4" is "Flush" and
    "Cancel" """

    name = unmarked(name.strip())[0]
    return re.sub(r"(?<=[A-Za-z)])\s*\d+(?:,\s*\d+)*$", "", name)


REGEX_MECHANISM = re.compile(r"\s+(?:using|over)\s+an?\s+[\w-]+\s+Mechanism$")


def command_set_name(name: str) -> str:
    """
    The name of a command set as the caption of its opcode table gives it, without
    "Command Set" or "I/O" after the name, and without the mechanism that the commands
    are used over. "NVM Command Set" is "NVM". "PCIe Commands using an Out-of-Band
    Mechanism" of MI 2.2 Figure 151 is "PCIe Commands", the term of MI 2.2 section 7,
    whose key differs from the key of the PCIe transport. The table "Opcodes for I/O
    Commands" of the Base specification lists the I/O commands of every I/O command set,
    which Base 2.4 calls common I/O commands. These commands are not a command set, and
    their name is "Common I/O".
    """

    name = REGEX_MECHANISM.sub("", name.strip())
    stripped = re.sub(r"(?:\s+Command Set)?(?:\s+I/O)?$", "", name)
    if name == "I/O":
        return "Common I/O"
    return stripped or name


def command_set_kind(name: str, document: str) -> CommandSetKind:
    """The kind of the command set named 'name' that 'document' lists"""

    if name == "Common I/O":
        return "common_io"
    if name == "Admin":
        return "admin"
    if "Management Interface Specification" in document:
        return "management_interface"
    if "Command Set Specification" in document:
        return "io"
    return "other"


def alias(name: str) -> str:
    """
    The key of a name: lower case, words joined by underscores, and "I/O" as one word;
    see key_of()
    """

    return key_of(name)


REGEX_HEX = re.compile(r"^(?P<hex>[0-9A-Fa-f]+)h$")


def byte_order_of(
    columns: Dict[str, str], description: str = ""
) -> Optional[Literal["big-endian", "little-endian"]]:
    """
    The byte order of a field that the columns "msb_byte" and "lsb_byte" of a byte
    diagram give, and otherwise the byte order that 'description' states, for example
    "This field is big endian". Returns None where neither gives one.
    """

    msb, lsb = columns.get("msb_byte", ""), columns.get("lsb_byte", "")
    if msb.isdigit() and lsb.isdigit() and int(msb) != int(lsb):
        return "big-endian" if int(msb) < int(lsb) else "little-endian"
    match = REGEX_BYTE_ORDER.search(description)
    if match:
        return "big-endian" if match[1].lower() == "big" else "little-endian"
    return None


REGEX_BYTE_ORDER = re.compile(
    r"\b(?:is|stored in|defined in) (big|little)[ -]endian\b", flags=re.IGNORECASE
)
ENCODINGS: List[Tuple[Literal["ascii", "utf-8", "uuid"], re.Pattern]] = [
    (
        "ascii",
        re.compile(
            r"\bASCII (?:encoded )?(?:null-terminated )?string\b|"
            r"\bASCII characters?\b"
        ),
    ),
    ("utf-8", re.compile(r"\bUTF-8 (?:null-terminated )?string\b")),
    (
        "uuid",
        re.compile(r"\b128-bit (?:Universally Unique Identifier \(UUID\)|UUID\b)"),
    ),
]


def encoding_of(description: str) -> Optional[Literal["ascii", "utf-8", "uuid"]]:
    """The encoding of the bytes of a field that 'description' states, or None"""

    text = " ".join(description.split())
    for encoding, pattern in ENCODINGS:
        if pattern.search(text):
            return encoding
    return None


# A footnote marker printed in superscript after the last sentence, which the
# text of the description gives as digits right after its full stop
REGEX_TRAILING_FOOTNOTES = re.compile(r"(?<=[A-Za-z][.)])(\d{1,2}(?:,\s*\d{1,2})*)$")


def footnoted(description: str) -> Tuple[str, List[int]]:
    """'description' without the footnote markers at its end, as "definition.1",
    and the numbers of those footnotes"""

    plain, marked = unmarked(description)
    if marked:
        return plain, marked
    match = REGEX_TRAILING_FOOTNOTES.search(description)
    if not match:
        return description, []
    numbers = [int(n) for n in re.findall(r"\d+", match[1])]
    return description[: match.start()], numbers


def bits_of(field: LayoutField, unit: Unit) -> ReadBits:
    name, named = unmarked(field.name or "", within=True)
    description, footnotes = footnoted(field.description)
    columns = {}
    for key, text in field.columns.items():
        columns[key], numbers = unmarked(text, within=True)
        footnotes += [n for n in numbers if n not in footnotes]
    return ReadBits(
        name=name if field.name is not None else None,
        acronym=field.acronym,
        unit=unit,
        upper=field.range.upper,
        lower=field.range.lower,
        range=field.range.text,
        description=description,
        footnotes=named + footnotes,
        section=field.section,
        elided=field.elided,
        columns=columns,
        # A field of one byte has no byte order, even where the description states one
        # for the bytes around it.
        byte_order=(
            None
            if unit == "bytes"
            and field.range.upper is not None
            and field.range.upper == field.range.lower
            else byte_order_of(columns, " ".join(description.split()))
        ),
        encoding=encoding_of(description),
        placements=[
            Placement(
                condition=p.condition,
                range=p.range.text if p.range else None,
                upper=p.range.upper if p.range else None,
                lower=p.range.lower if p.range else None,
            )
            for p in field.placements
        ],
        fields=unions_of(
            [
                bits_of(nested_field, nested.unit)
                for nested in field.layouts
                for nested_field in nested.fields
            ]
        ),
        values=[value_of(entry) for entry in field.values],
        cases=[
            ReadCase(
                selector=case.selector,
                when=[Selected(name=name) for name in case.when],
                otherwise=case.otherwise,
                name=case.name,
                acronym=case.acronym,
                description=case.description,
                values=[value_of(entry) for entry in case.values],
                fields=unions_of(
                    [
                        bits_of(nested_field, nested.unit)
                        for nested in case.layouts
                        for nested_field in nested.fields
                    ]
                ),
            )
            for case in field.cases
        ],
    )


def value_of(entry: Dict[str, str]) -> "Entry":
    """A value a field takes, its value typed where it has a form, as "000b",
    "1h" or "2" """

    value = entry_of(entry)
    typed = typed_of(value.value)
    if typed:
        value.typed[value.value_column] = typed
    return value


def fields_of(layout: Layout) -> List[ReadBits]:
    fields = unions_of([bits_of(field, layout.unit) for field in layout.fields])
    number_unions(fields)
    return fields


def same_structure(a: ReadBits, b: ReadBits) -> bool:
    """Whether fields are of one structure, as a table listing the fields of
    several, by a column naming the structure of each, gives fields of others"""

    for column in set(a.columns) & set(b.columns):
        if "structure" in column and a.columns[column] != b.columns[column]:
            return False
    return True


def number_unions(fields: List[ReadBits], start: int = 0) -> int:
    """Number the unions of 'fields' and of the fields nested in them anew, in
    one sequence, so that no two unions of a layout have the same number;
    returns the next number"""

    renumbered: Dict[int, int] = {}
    for field in fields:
        if field.union is not None:
            if field.union not in renumbered:
                renumbered[field.union] = start + len(renumbered)
            field.union = renumbered[field.union]
    start += len(renumbered)
    for field in fields:
        start = number_unions(field.fields, start)
    return start


def unions_of(fields: List[ReadBits]) -> List[ReadBits]:
    """
    'fields' with those sharing bits, of a section, made alternatives of a
    union: the fields of bits some other shares are a region, and each is,
    in the order of the table, of the first alternative of its region whose
    fields it shares no bits with
    """

    def overlaps(a: ReadBits, b: ReadBits) -> bool:
        return (
            a.lower is not None
            and b.lower is not None
            and a.upper is not None
            and b.upper is not None
            and a.lower <= b.upper
            and b.lower <= a.upper
        )

    unions = 0
    for section in dict.fromkeys(f.section for f in fields):
        these = [f for f in fields if f.section == section and f.lower is not None]
        # The regions: fields joined by sharing bits, directly or through others
        regions: List[List[ReadBits]] = []
        for field in these:
            joined = [
                r
                for r in regions
                if any(overlaps(field, f) and same_structure(field, f) for f in r)
            ]
            region = [field] + [f for r in joined for f in r]
            regions = [r for r in regions if r not in joined] + [region]
        for region in regions:
            if len(region) < 2:
                continue
            alternatives: List[List[ReadBits]] = []
            for field in sorted(region, key=fields.index):
                at = next(
                    (
                        i
                        for i, alternative in enumerate(alternatives)
                        if not any(
                            overlaps(field, f) and same_structure(field, f)
                            for f in alternative
                        )
                    ),
                    None,
                )
                if at is None:
                    alternatives.append([field])
                    at = len(alternatives) - 1
                else:
                    alternatives[at].append(field)
                field.union, field.alternative = unions, at
            unions += 1
    return fields


# The dwords of the pointers, where the common command format puts them; their
# figures do not say
POINTERS = {"metadata_pointer": (4, 5), "data_pointer": (6, 9)}


# An acronym is letters and digits, in parts joined by "-", "_", "/" or ".", as
# "SLBA", "128CCS" or "NVMSETID"
REGEX_ACRONYM = re.compile(r"^[A-Za-z0-9]+(?:[-_/.][A-Za-z0-9]+)*$")


def checked(
    fields: List[ReadBits],
    width: Optional[int],
    source: Source,
    of: str = "its dwords",
) -> Tuple[List[Bits], List[Erratum], List[str]]:
    """
    The fields made from the rows of a layout, the errata of those that are
    not what fields must be, and what is said of the rows naming no field: an
    acronym that is not one is left out, and a row whose range is none, by
    senfd.ranges, is left out whole, as one of reversed bounds or beyond the
    'width' in bits of what it is 'of', its dwords or the bytes holding it;
    fields sharing bits are not errata, as a layout can give either of two,
    as an IPv4 or an IPv6 address
    """

    errata: List[Erratum] = []
    unnamed: List[str] = []
    kept: List[Bits] = []
    for field in fields:
        what = f"{field.range} {field.name or ''}".strip()
        acronym = field.acronym
        if acronym and not REGEX_ACRONYM.match(acronym):
            errata.append(
                Erratum(
                    code="acronym",
                    message=f"Field {what}: acronym '{acronym}' is not one",
                    found=acronym,
                    source=source,
                )
            )
            acronym = None
        try:
            try:
                rng = senfd.ranges.parse(field.unit, field.range, width)
            except senfd.ranges.RangeError as exc:
                # A ")" that closes no "(" is an erratum, for example in
                # "(NUMENT-1)*32+63)" of Base 2.4 Figure 361, and the range is read
                # without it.
                closed = unopened(field.range)
                if closed == field.range:
                    raise
                rng = senfd.ranges.parse(field.unit, closed, width)
                errata.append(
                    Erratum(
                        code=exc.code,
                        message=f"Field {what}: {exc}",
                        found=field.range,
                        source=source,
                    )
                )
            made = senfd.fields.identity(field.name, acronym, field.description)
        except senfd.ranges.RangeError as exc:
            said = f"{exc} of {of}" if exc.code == "range-outside" else str(exc)
            errata.append(
                Erratum(
                    code=exc.code,
                    message=f"Field {what}: {said}",
                    found=field.range,
                    source=source,
                )
            )
            continue
        except senfd.fields.Unnamed as exc:
            if not field.fields:
                unnamed.append(f"Field {what}: {exc}")
                continue
            # A row with a range and a nested table but no name, for example
            # a byte whose bits are fields, is named after its range
            one = rng.width == 1
            unit = field.unit[:-1] if one else field.unit
            made = senfd.fields.Identity("field", f"{unit.capitalize()} {field.range}")
        # Bits nested in a range of bytes lie within its bytes
        within, holding = None, "its dwords"
        if rng.unit == "bytes" and rng.width is not None:
            within = 8 * rng.width
            holding = f"byte {field.range}" if within == 8 else f"bytes {field.range}"
        nested, nested_errata, nested_unnamed = checked(
            field.fields, within, source, holding
        )
        errata += nested_errata
        unnamed += nested_unnamed
        cases = []
        for case in field.cases:
            laid_out, case_errata, case_unnamed = checked(
                case.fields, within, source, holding
            )
            relative_to(rng, laid_out)
            errata += case_errata
            unnamed += case_unnamed
            is_a = senfd.fields.identity(case.name, None).role if case.name else "field"
            made_case = case.model_dump(exclude={"fields"})
            cases.append(Case(role=is_a, fields=laid_out, **made_case))
        named_by_its_text = field.name is None and made.role == "field"
        kept.append(
            Bits(
                name=made.name,
                acronym=made.acronym,
                unit=rng.unit,
                role=made.role,
                kind=rng.kind,
                upper=rng.upper,
                lower=rng.lower,
                range=field.range,
                formula=rng.formula,
                width=rng.width,
                description="" if named_by_its_text else field.description,
                section=field.section,
                elided=field.elided,
                columns=field.columns,
                fields=nested,
                union=field.union,
                alternative=field.alternative,
                placements=field.placements,
                byte_order=field.byte_order,
                encoding=field.encoding,
                footnotes=field.footnotes,
                values=field.values,
                cases=cases,
            )
        )

    for field_made in kept:
        for case_made in field_made.cases:
            decide(case_made, kept)
    # A row that the figure leaves out, for example the last entry of a list whose range
    # is reversed, may have ended a run of two.
    whole = len(kept) == len(fields)
    for disagreeing in arrays_of(kept, pairs=whole):
        errata.append(Erratum(code="acronym", message=disagreeing, source=source))
    return kept, errata, unnamed


def relative_to(holder: "senfd.ranges.Range", fields: List[Bits]) -> None:
    """
    Make the ranges of 'fields', the fields of a case of the field of the range 'holder',
    relative to that field where the figure gives them relative to the structure: where
    they all lie within the field and one lies beyond its width, as PRP2 at bytes 39:32
    of DPTR at bytes 39:24 of Base 2.4 Figure 93, which is bytes 15:08 of DPTR
    """

    spans = [f for f in fields if f.kind == "span"]
    if holder.kind != "span" or holder.upper is None or holder.lower is None or not spans:
        return
    if any(f.unit != holder.unit for f in spans):
        return
    width = holder.upper - holder.lower + 1
    inside = all(
        holder.lower <= (f.lower or 0) and (f.upper or 0) <= holder.upper for f in spans
    )
    if inside and any((f.upper or 0) >= width for f in spans):
        for field in spans:
            field.lower = (field.lower or 0) - holder.lower
            field.upper = (field.upper or 0) - holder.lower
            field.range = f"{field.upper:02d}:{field.lower:02d}"
            if field.upper == field.lower:
                field.range = f"{field.lower:02d}"


def decide(case: Case, fields: List[Bits]) -> None:
    """Set the selector of 'case' to the acronym of the controlling field,
    found among 'fields', and set the number of each value in 'case.when'.
    The number comes from the controlling field's value of that name, or from
    the code that the case writes in place of a name, also where the
    controlling field is of another figure, as PSDT of CDW0 for the Data
    Pointer."""

    names = (alias(case.selector),)
    by = next(
        (
            f
            for f in fields
            if alias(f.name) in names or alias(f.acronym or "") in names
        ),
        None,
    )
    numbers: Dict[str, int] = {}
    if by is not None:
        case.selector = by.acronym or by.name
    for value in by.values if by is not None else []:
        typed = value.typed.get(value.value_column)
        if typed is None or typed.lower is None or typed.lower != typed.upper:
            continue
        for name in value_names(value):
            numbers.setdefault(alias(name), typed.lower)
    for selected in case.when:
        # A row may give the code, for example "01h", instead of the name
        code = typed_of(selected.name)
        if code and code.kind in ("identifier", "number") and code.lower == code.upper:
            selected.value = code.lower
        else:
            selected.value = numbers.get(alias(selected.name))


def numbered(text: Optional[str]) -> List[Tuple[str, int, str]]:
    """Each split of 'text' around a number in it: the text before the
    number, the number, and the text after it, for example ("LBAF", 0, "")
    for "LBAF0" """

    name = text or ""
    decimal = [
        (name[: match.start()], int(match[0]), name[match.end() :])
        for match in re.finditer(r"\d+", name)
    ]
    # The hexadecimal indexes come after the decimal ones, so that "10" is ten, and so
    # that the last split of "Format 2h Enable" leaves no "h". A hexadecimal index ends
    # in "h", for example "C1h" of "Performance Attribute C1h Identifier", or it has two
    # digits of which one is a letter, for example "FF" of "Vendor Specific Protocol
    # FF".
    hexadecimal = [
        (name[: match.start()], int(match[1] or match[2], 16), name[match.end() :])
        for match in re.finditer(
            r"\b(?:([0-9A-F]+)h|((?=[0-9]?[A-F])[0-9A-F]{2}))\b", name
        )
    ]
    return decimal + hexadecimal


def hexadecimal_acronym(spans: List[Tuple[int, Bits]]) -> Optional[str]:
    """
    The acronym of entries numbered by name, where every acronym holds the index of its
    entry as two hexadecimal digits at the same place, for example VSPF0 and VSPFF.
    Returns None otherwise, for example for PAC1HI and PACFFHI, the entries C1h and FFh.
    """

    parts = set()
    for index, field in spans:
        acronym, digits = field.acronym or "", f"{index:02X}"
        if acronym.count(digits) != 1:
            return None
        before, _, after = acronym.partition(digits)
        parts.add((before, after))
    return "".join(parts.pop()) if len(parts) == 1 else None


def arrays_of(fields: List[Bits], pairs: bool = True) -> List[str]:
    """
    Set 'array' on each of 'fields' that is an entry of an array. The entries are
    adjacent fields whose acronyms, or names, differ only by an index, decimal or
    hexadecimal, and the figure can leave out rows between two of them. Each entry has
    the same width and lies at the offset that its index gives. A formula can give the
    last entry, for example "Entry NUMENT-1", and the array then has no count. Where the
    acronyms give other indexes than the names, the names give the indexes, for example
    VSP15, VSP1 and VSP0 of "Vendor Specific Protocol FF", "F1" and "F0" of Base 2.4
    Figure 516. Returns a message for each such run, for a candidate erratum.
    """

    def entry(field: Bits, of: str, before: str, after: str) -> Optional[int]:
        """The index of 'field' where its name is 'before', a number and
        'after', and otherwise None"""

        for prefix, number, suffix in numbered(getattr(field, of)):
            if (prefix, suffix) == (before, after) and field.kind == "span":
                return number
        return None

    def run_of(at: int, of: str):
        """
        The run of entries around the left-out field at 'at', compared by the attribute
        'of', as the tuple (start, indexes, before, after), or None
        """

        last, above = fields[at], fields[at - 1]
        text = getattr(last, of) or ""
        for before, _, after in numbered(getattr(above, of)):
            closes = last.kind == "formula" and text.startswith(before)
            if entry(last, of, before, after) is not None or (
                closes and text.endswith(after) and len(text) > len(before + after)
            ):
                break
        else:
            return None

        start, end = at - 1, at
        while start and entry(fields[start - 1], of, before, after) is not None:
            start -= 1
        while (
            last.kind == "span"
            and end + 1 < len(fields)
            and entry(fields[end + 1], of, before, after) is not None
        ):
            end += 1
        run = fields[start : end + 1]
        indexes = [entry(field, of, before, after) for field in run]
        spans = [(i, f) for i, f in zip(indexes, run) if i is not None]
        first, lowest = min(spans, key=lambda span: span[0])
        stride = lowest.width or 0
        # Where the formula of the last entry gives a width and the entries lie at
        # offsets of that width, the width is the stride. For example, Descriptors 1 and
        # 2 of Base 2.4 Figure 384 are 520 and 22 bytes at offsets 260 bytes apart.
        # misnumbered() reports them.
        if (
            last.kind == "formula"
            and last.width
            and all(
                f.lower == (lowest.lower or 0) + (i - first) * last.width
                for i, f in spans
            )
        ):
            return start, indexes, before, after
        # One entry of another width at its place, for example Host Fabric Interface
        # Descriptor 2 of Boot 1.4 Figure 11 with 33 bytes, is still an entry.
        # misnumbered() reports it as a candidate erratum.
        if (
            not stride
            or any(
                f.lower != (lowest.lower or 0) + (i - first) * stride for i, f in spans
            )
            or sum(f.width != stride for _, f in spans) > (1 if len(run) > 2 else 0)
        ):
            return None
        return start, indexes, before, after

    disagreeing: List[str] = []
    for at, last in enumerate(fields):
        if not last.elided or at == 0 or last.array or fields[at - 1].array:
            continue
        if fields[at - 1].kind != "span":
            continue
        by_acronym = run_of(at, "acronym") if fields[at - 1].acronym else None
        by_name = run_of(at, "name")
        found, of = by_acronym, "acronym"
        if by_name and (not by_acronym or by_acronym[:2] != by_name[:2]):
            if by_acronym:
                start, indexes = by_acronym[:2]
                listed = fields[start : start + len(indexes)]
                disagreeing.append(
                    "The acronyms "
                    + ", ".join(f.acronym or "" for f in listed)
                    + " give other indexes than the names "
                    + ", ".join(f'"{f.name}"' for f in listed)
                )
            found, of = by_name, "name"
        if not found:
            continue
        start, indexes, before, after = found
        run = fields[start : start + len(indexes)]
        spans = [(i, f) for i, f in zip(indexes, run) if i is not None]
        first, lowest = min(spans, key=lambda span: span[0])
        name = next(
            (b + a for b, n, a in reversed(numbered(lowest.name)) if n == first),
            lowest.name,
        )
        whole = len(spans) == len(run)
        acronym = before + after if of == "acronym" else hexadecimal_acronym(spans)
        for index, field in zip(indexes, run):
            field.array = Array(
                name=" ".join(name.split()),
                acronym=acronym,
                index=index,
                first=first,
                count=max(i for i, _ in spans) - first + 1 if whole else None,
                stride=next(
                    (f.width for f in run if f.kind == "formula" and f.width),
                    lowest.width or 0,
                ),
                lower=lowest.lower or 0,
            )
    listed_arrays(fields, pairs)
    variable_arrays(fields)
    grouped_arrays(fields)
    return disagreeing


REGEX_LAST_INDEX = re.compile(r"[A-Za-z][\w+-]*")


def given_run(
    fields: List[Bits], at: int, step: int, of: str
) -> Tuple[List[int], List[Optional[int]], str, str]:
    """
    The entries from 'at', at every 'step' fields, whose attribute 'of' differs only by
    the next index, and whose ranges the data gives, except the range of the first
    entry. Returns the positions, the indexes, and the text before and after the index.
    A last entry numbered by a name, for example "Entry NUMREC-1", has the index None.
    """

    best: Tuple[List[int], List[Optional[int]], str, str] = ([at], [], "", "")
    for before, number, after in numbered(getattr(fields[at], of)):
        # An acronym that is only a hexadecimal index, for example ED, does not name an
        # entry.
        if not re.search(r"[A-Za-z]", before + after):
            continue
        positions: List[int] = [at]
        indexes: List[Optional[int]] = [number]
        while positions[-1] + step < len(fields):
            other = fields[positions[-1] + step]
            found = [
                n
                for b, n, a in numbered(getattr(other, of))
                if (b, a) == (before, after)
            ]
            if not found or found[0] != number + len(indexes) or other.kind == "span":
                break
            positions.append(positions[-1] + step)
            indexes.append(found[0])
        if positions[-1] + step < len(fields):
            last = fields[positions[-1] + step]
            text = getattr(last, of) or ""
            middle = text[len(before) : len(text) - len(after)]
            if (
                last.kind != "span"
                and text.startswith(before)
                and text.endswith(after)
                and REGEX_LAST_INDEX.fullmatch(middle)
            ):
                positions.append(positions[-1] + step)
                indexes.append(None)
        if len(positions) > len(best[0]):
            best = (positions, indexes, before, after)
    return best


def variable_arrays(fields: List[Bits]) -> None:
    """
    Set 'array' on the fields of each run of two or more entries that are numbered by
    consecutive indexes and whose ranges the data gives, by a formula or by a text.
    Examples are ANA Group Descriptor 0 at "n:16" and ANA Group Descriptor 1 at "m:n+1"
    of Base 2.4 Figure 230, and Media Unit Status Descriptor 0 and 1 at "NOTE 1" of
    Figure 263. Such an array has no count, and it has a stride only where the entries
    have one width. A last entry numbered by a name is an entry without an index, for
    example "ANA Group Descriptor N" after the others, or "Entry N" after "Entry 0" of
    Figure 322. Where the entries of two such runs alternate, for example Zone
    Descriptor 0 and Zone Descriptor Extension 0 of ZNS 1.4 Figure 37, the runs are two
    arrays without a stride. A range "n/a", for example of CDW14 and CDW15 of MI 2.2
    Figure 49, is not a range that the data gives.
    """

    def usable(run: List[Bits]) -> bool:
        return not any(
            f.array or (f.kind == "open" and f.range.strip().casefold() == "n/a")
            for f in run
        ) and any(f.kind != "span" for f in run)

    def assign(positions, indexes, before, after, of, stride) -> None:
        run = [fields[i] for i in positions]
        first = run[0]
        name = (
            before + after
            if of == "name"
            else next(
                (
                    b + a
                    for b, n, a in reversed(numbered(first.name))
                    if n == indexes[0]
                ),
                first.name or "",
            )
        )
        for index, field in zip(indexes, run):
            field.array = Array(
                name=" ".join(name.split()),
                acronym=before + after if of == "acronym" else None,
                index=index,
                first=indexes[0],
                stride=stride,
                lower=first.lower,
            )

    at = 0
    while at < len(fields):
        of = "acronym" if fields[at].acronym else "name"
        positions, indexes, before, after = given_run(fields, at, 1, of)
        if of == "acronym" and not all(fields[i].acronym for i in positions):
            of = "name"
            positions, indexes, before, after = given_run(fields, at, 1, of)
        run = [fields[i] for i in positions]
        if len(run) >= 2 and usable(run):
            # Entries of one width at offsets that the data gives have that width as
            # their stride, for example the two bytes of each Channel Identifier of
            # Figure 264 from CIO.
            widths = {f.width for f in run}
            stride = widths.pop() if len(widths) == 1 else None
            assign(positions, indexes, before, after, of, stride)
            at = positions[-1] + 1
            continue
        if at + 1 < len(fields):
            one = given_run(fields, at, 2, "name")
            two = given_run(fields, at + 1, 2, "name")
            if (
                len(one[0]) >= 2
                and one[1] == two[1]
                and two[0] == [i + 1 for i in one[0]]
                and one[2:] != two[2:]
                and usable([fields[i] for i in one[0] + two[0]])
            ):
                assign(*one, "name", None)
                assign(*two, "name", None)
                at = two[0][-1] + 1
                continue
        at += 1


def grouped_arrays(fields: List[Bits]) -> None:
    """
    Make the entries of an array of the rows of a layout that a column groups by a name
    and an index, for example "Source Range 0", "Source Range 1" and "Source Range 127"
    of NVM 1.3 Figure 40. A blank cell continues the group above it. Where each group
    lies at the offset that its index gives, by the size of the first group, the groups
    are the entries of an array from the first index to the last. The rows of each group
    become one field, the entry, whose fields are the rows at offsets from the start of
    the entry.
    """

    for column in {c for f in fields for c in f.columns}:
        labels: List[Optional[Tuple[str, int]]] = []
        for field in fields:
            match = re.fullmatch(r"(.+?) (\d+)", field.columns.get(column, ""))
            if match:
                labels.append((match[1], int(match[2])))
            elif field.columns.get(column, "").strip() or not labels:
                labels.append(None)
            else:
                labels.append(labels[-1])
        if None in labels or len({label[0] for label in labels}) != 1:  # type: ignore
            continue
        starts: Dict[int, int] = {}
        for (_, index), field in zip(labels, fields):  # type: ignore
            if field.kind == "span" and field.lower is not None:
                starts[index] = min(starts.get(index, field.lower), field.lower)
        indexes = sorted(starts)
        if len(indexes) < 2:
            continue
        first, second = indexes[0], indexes[1]
        stride = (starts[second] - starts[first]) // (second - first)
        if stride <= 0 or any(
            starts[i] != starts[first] + (i - first) * stride for i in indexes
        ):
            continue
        name = labels[0][0]  # type: ignore
        grouped: Dict[int, List[Bits]] = {}
        for (_, index), field in zip(labels, fields):  # type: ignore
            grouped.setdefault(index, []).append(field)
        entries = []
        for index, rows in grouped.items():
            start = starts[index]
            upper, lower = start + stride - 1, start
            inner = []
            for row in rows:
                moved = row.model_copy(deep=True)
                moved.columns = {k: v for k, v in row.columns.items() if k != column}
                if moved.kind == "span" and moved.upper is not None:
                    moved.lower = (moved.lower or 0) - start
                    moved.upper -= start
                    moved.range = f"{moved.upper:02d}:{moved.lower:02d}"
                    if moved.upper == moved.lower:
                        moved.range = f"{moved.lower:02d}"
                inner.append(moved)
            entries.append(
                Bits(
                    name=f"{name} {index}",
                    unit=rows[0].unit,
                    role="field",
                    kind="span",
                    upper=upper,
                    lower=lower,
                    range=f"{upper}:{lower}",
                    width=stride,
                    elided=any(row.elided for row in rows),
                    fields=inner,
                    array=Array(
                        name=name,
                        index=index,
                        first=first,
                        count=indexes[-1] - first + 1,
                        stride=stride,
                        lower=starts[first],
                    ),
                )
            )
        fields[:] = entries
        return


def unopened(text: str) -> str:
    """'text' without each ')' that has no '(' before it to close"""

    kept, depth = [], 0
    for char in text:
        if char == ")" and depth == 0:
            continue
        depth += {"(": 1, ")": -1}.get(char, 0)
        kept.append(char)
    return "".join(kept)


def run_at(fields: List[Bits], at: int) -> Tuple[int, List[int], str]:
    """
    The run of fields from 'at' whose acronyms, or otherwise names, differ only by an
    index, and that are as wide as the first field, for example TSEN1 to TSEN8. Returns
    the position after the run, the indexes, and the acronym or name without the index.
    """

    first = fields[at]
    longest: Tuple[int, List[int], str] = (at + 1, [], "")
    for of in ("acronym", "name"):
        for before, number, after in numbered(getattr(first, of)):
            end, indexes = at + 1, [number]
            while end < len(fields):
                other = fields[end]
                found = [
                    n
                    for b, n, a in numbered(getattr(other, of))
                    if (b, a) == (before, after)
                ]
                if not found or other.width != first.width or other.kind != first.kind:
                    break
                indexes.append(found[0])
                end += 1
            if len(indexes) > len(longest[1]):
                longest = (end, indexes, before + after)
        if len(longest[1]) > 1:
            break
    return longest


def listed_arrays(fields: List[Bits], pairs: bool = True) -> None:
    """
    Set 'array' on the fields of each run of two or more that a figure lists in full,
    where each field is numbered by the next index, is as wide as the others, and lies
    at the offset that its index gives. Examples are TSEN1 to TSEN8 of the SMART /
    Health Information log page, an array of 8, and TMT1TC and TMT2TC, an array of 2.
    Where the figure leaves out a row, 'pairs' is false, and a run of two is not an
    array: Exported Controller Association Descriptor 0 and 1 of Base 2.4 Figure 404
    begin a list whose last entry has a reversed range.
    """

    at = 0
    while at < len(fields):
        end, indexes, _ = run_at(fields, at)
        run = fields[at:end]
        if (
            len(run) < (2 if pairs else 3)
            or any(f.array or f.kind != "span" or f.lower is None for f in run)
            or sorted(indexes) != list(range(min(indexes), max(indexes) + 1))
        ):
            at = max(end, at + 1) if len(run) > 1 else at + 1
            continue
        first = min(indexes)
        lowest = run[indexes.index(first)]
        stride = lowest.width or 0
        lower = lowest.lower or 0
        if stride and all(
            f.lower == lower + (i - first) * stride for i, f in zip(indexes, run)
        ):
            of = "acronym" if all(f.acronym for f in run) else "name"
            stems = {
                (b + a)
                for i, f in zip(indexes, run)
                for b, n, a in numbered(getattr(f, of))
                if n == i
            }
            name = next(
                (b + a for b, n, a in reversed(numbered(lowest.name)) if n == first),
                lowest.name or "",
            )
            acronym = stems.pop() if of == "acronym" and len(stems) == 1 else None
            for index, field in zip(indexes, run):
                field.array = Array(
                    name=" ".join(name.split()),
                    acronym=acronym,
                    index=index,
                    first=first,
                    count=len(run),
                    stride=stride,
                    lower=lower,
                )
        at = end


def maxima_of(fields: List[Bits], mentions: List[str]) -> None:
    """Set the maximum of each array of 'fields' without a count that one of
    'mentions', the paragraphs referring to their figure, states as "up to
    511 Zone Identifier entries" or "up to 511 Lost Host Communication
    Entries" """

    for field in fields:
        array = field.array
        if array is None or array.count is not None:
            continue
        name = re.escape(array.name)
        if array.name.endswith("Entry"):
            name = re.escape(array.name[: -len("Entry")]) + "(?:Entry|Entries)"
        pattern = re.compile(
            rf"\bup to (\d+) {name}(?:\s+entries)?\b", flags=re.IGNORECASE
        )
        found = {int(m[1]) for text in mentions for m in pattern.finditer(text)}
        if not found:
            found = counted_by(field, fields)
        if len(found) == 1:
            array.maximum = found.pop()


def link_counts(fields: List[Bits]) -> None:
    """
    Set 'counted_by' on the arrays of 'fields' that have no count, where the last entry
    names one field of 'fields' by its acronym in place of its index, as NUMCIDS of
    "Controller Identifier NUMCIDS-1"
    """

    acronyms = {f.acronym for f in fields if f.acronym}
    last: Dict[str, Bits] = {}
    for field in fields:
        if field.array is not None and field.array.count is None:
            last[field.array.name] = field
    for name, entry in last.items():
        words = (entry.name or "").replace(name, " ", 1) if entry.name else ""
        named = set(re.findall(r"\b[A-Za-z][A-Za-z0-9]*\b", words)) & acronyms
        if len(named) != 1:
            continue
        (counter,) = named
        for field in fields:
            if field.array is not None and field.array.name == name:
                field.array.counted_by = counter


def counted_by(entry: Bits, fields: List[Bits]) -> set:
    """
    The maxima that the field counting the entries of the array of 'entry' states, for
    example "up to 127 entries" of NUMENT in Base 2.4 Figure 361, whose last entry is
    "SC Entry NUMENT-1"
    """

    array = entry.array
    if array is None:
        return set()
    last = next(
        (f for f in reversed(fields) if f.array and f.array.name == array.name), entry
    )
    named = set(re.findall(r"\b[A-Z][A-Z0-9]+\b", (last.name or "")[len(array.name) :]))
    return {
        int(m[1])
        for field in fields
        if field.acronym and field.acronym in named
        for m in re.finditer(r"\bup to (\d+) entries\b", field.description)
    }


def took(
    document: "SpecDocument",
    errata: List[Erratum],
    unnamed: List[str],
    source: Source,
) -> None:
    """What making the fields of a figure found, taken into 'document'"""

    document.errata += errata
    document.diagnostics += [
        note("field-name", f"{cite(source)}: {said}") for said in unnamed
    ]


# The kinds of a figure that lay out the whole of something, by its caption;
# another can list some fields of it, as those a reference value is given for
WHOLE = ("data_structure", "log_page", "register")


def misnumbered(fields: List[Bits], unit: str, source: Source) -> List[Erratum]:
    """
    The candidate errata of a layout whose numbered fields differ in width, and of a
    layout of more than 256 bytes whose size is one byte more than a power of two. Boot
    1.4 Figure 11 gives "Host Fabric Interface Descriptor 1", "2" and "n" 32, 33 and 32
    bytes, and the descriptor of another width than the others is an erratum. Where the
    formula of the last field gives a width, the fields of another width than that one
    are errata. NVM 1.3 Figure 134 is 4097 bytes, and its last field is "4096:768
    Reserved".
    """

    errata: List[Erratum] = []
    runs: Dict[str, List[Bits]] = {}
    for field in fields:
        match = re.fullmatch(r"(.+?)(?<!Figure) (?:\d+|[nN])", field.name or "")
        if match and field.width:
            runs.setdefault(match[1], []).append(field)
    for run in runs.values():
        widths = [f.width for f in run]
        common = max(set(widths), key=widths.count)
        # The formula of the last entry gives the width of every entry, for example 260
        # bytes for "Exported NVM Subsystem Descriptor N" of Base 2.4 Figure 384, whose
        # Descriptors 1 and 2 are 520 and 22 bytes.
        given = {f.width for f in run if f.kind == "formula"}
        others = "the other fields numbered so are"
        if len(given) == 1 and len(run) >= 3:
            common = given.pop()
            others = "the formula of the last field numbered so gives"
        elif len(run) < 3 or widths.count(common) * 2 <= len(run):
            continue
        for field in run:
            if field.width != common:
                errata.append(
                    Erratum(
                        code="range",
                        message=f"Field {field.range} {field.name}: {field.width} "
                        f"{unit} where {others} {common}",
                        found=field.range,
                        source=source,
                    )
                )
    bounds = [f.upper for f in fields if f.kind == "span" and f.upper is not None]
    size = max(bounds) + 1 if bounds else 0
    if size > 256 and (size - 1) & (size - 2) == 0:
        last = next(f for f in fields if f.upper == size - 1)
        errata.append(
            Erratum(
                code="range",
                message=f"Field {last.range} {last.name or ''}".rstrip()
                + f": the layout is {size} {unit}, one more than {size - 1}",
                found=last.range,
                source=source,
            )
        )
    return errata


def shared_acronyms(fields: List[Bits], source: Source) -> List[Erratum]:
    """
    The candidate errata of a structure where one acronym, at any depth, names two
    fields of different names, for example AHATSDPS of Base 2.4 Figure 516 for both "...
    Protocol Status" and "... Protocol Support"
    """

    names: Dict[str, List[str]] = {}

    def walk(fields: List[Bits]) -> None:
        for field in fields:
            if field.acronym and field.role == "field":
                named = names.setdefault(field.acronym, [])
                if field.name not in named:
                    named.append(field.name)
            walk(field.fields)
            for case in field.cases:
                walk(case.fields)

    walk(fields)
    return [
        Erratum(
            code="acronym",
            message=f"{acronym} is the acronym of "
            + " and ".join(f'"{name}"' for name in named),
            found=acronym,
            source=source,
        )
        for acronym, named in names.items()
        if len(named) > 1
    ]


def starts_at_zero(fields: List[Bits]) -> bool:
    """Whether the first field of 'fields' of known bounds starts at 0"""

    spans = [f for f in fields if f.kind == "span" and f.lower is not None]
    return bool(spans) and spans[0].lower == 0


def uncovered(fields: List[Bits], unit: str, source: Source) -> List[Erratum]:
    """
    The errata of a layout whose fields do not lie one after another: bits or
    bytes of no field between two fields next in the table, where the figure
    leaves no rows out between them and no field of a formula or an open
    range lies between them. Fields sharing bits, as the alternatives of a
    union or the fields of several structures in one table, leave none.
    """

    spans = [f for f in fields if f.kind == "span" and f.lower is not None]
    descending = len(spans) > 1 and (spans[0].lower or 0) > (spans[-1].lower or 0)
    errata: List[Erratum] = []
    after: Optional[int] = None  # The first bit or byte after those before
    unknown = False  # Whether a field of no known bounds lies between
    elided = False  # Whether the figure leaves rows out between
    for field in fields[::-1] if descending else fields:
        # Rows left out are marked on the field after them in the table
        elided = elided or (field.elided and not descending)
        if field.kind != "span" or field.upper is None or field.lower is None:
            unknown = True
        else:
            if after is not None and field.lower > after and not (unknown or elided):
                missing = f"{unit[:-1].capitalize()} {after} is"
                if field.lower - 1 > after:
                    missing = f"{unit.capitalize()} {after} to {field.lower - 1} are"
                named = f"{field.range} {field.name or ''}".strip()
                errata.append(
                    Erratum(
                        code="layout-gap",
                        message=f"{missing} of no field, before {named}",
                        found=field.range,
                        source=source,
                    )
                )
            after = max(after or 0, field.upper + 1)
            unknown = elided = False
        elided = elided or (field.elided and descending)
    return errata


def uncovered_entries(fields: List[Bits], unit: str, source: Source) -> List[Erratum]:
    """
    The errata of uncovered() of the entries that grouped_arrays() made, each entry's
    fields at the offsets of the figure, as the bytes of no field of Source Range 1 of
    SLM 1.3 Figure 13
    """

    errata = []
    for entry in fields:
        if entry.array is None or not entry.fields or entry.lower is None:
            continue
        placed = []
        for field in entry.fields:
            moved = field.model_copy()
            if field.kind == "span" and field.upper is not None:
                moved.lower = (field.lower or 0) + entry.lower
                moved.upper = field.upper + entry.lower
                moved.range = f"{moved.upper}:{moved.lower}"
            placed.append(moved)
        errata += uncovered(placed, unit, source)
    return errata


def source_of(figure: NormalizedFigure, stem: str) -> Source:
    return Source(
        document=stem,
        figure_nr=figure.figure_nr,
        page_nr=figure.page_nr,
        pdf_page=figure.pdf_page,
        section=figure.section,
        section_title=figure.section_title,
    )


# What the normalised figure document notes that is a defect of the document
# rather than a variant of writing, by the code of the erratum it is
NOTED_ERRATA: Dict[str, ErratumCode] = {"acronym-open": "acronym"}


def noted_errata(normalized: NormalizedFigureDocument, stem: str) -> List[Erratum]:
    """The candidate errata among the diagnostics of 'normalized', which has
    read what the document means, as the acronym of "Name (ACRONYM", so that
    the data model has it, and the authors are told of the defect"""

    figures = {figure.figure_nr: figure for figure in normalized.figures}
    errata = []
    for diagnostic in normalized.diagnostics:
        figure = figures.get(diagnostic.figure_nr or 0)
        if diagnostic.code not in NOTED_ERRATA or figure is None:
            continue
        quoted = re.findall(r"'([^']*)'", diagnostic.message)
        errata.append(
            Erratum(
                code=NOTED_ERRATA[diagnostic.code],
                message=diagnostic.message,
                found=quoted[-1] if quoted else "",
                source=source_of(figure, stem),
            )
        )
    return errata


def add_figure(document: SpecDocument, figure: NormalizedFigure, stem: str) -> None:
    source = source_of(figure, stem)
    subject = figure.subject
    # A register whose layout is a figure of a format it shares, as VS of the
    # Specification Version Descriptor, is named by the title of its section
    if (
        subject.kind == "other"
        and figure.shape == "layout"
        and figure.layout is not None
        and figure.layout.unit == "bits"
        and figure.section_title
    ):
        from senfd.normalize import normalize_caption, parse_caption

        titled = parse_caption(normalize_caption(figure.section_title)[0])
        if titled.kind == "register":
            subject = titled

    if figure.shape == "opcode" and subject.kind == "opcodes" and subject.name:
        set_name = command_set_name(subject.name)
        command_set = document.command_sets.setdefault(
            alias(set_name),
            CommandSet(name=set_name, kind=command_set_kind(set_name, source.document)),
        )
        for row in figure.entries:
            entry = entry_of(row, "opcode")
            opcode = unmarked(row.get("opcode", ""))[0]
            match = REGEX_HEX.match(opcode)
            name = without_footnote(row.get("command", ""))
            if not name:
                continue
            if not match:
                # Reserved and vendor specific opcodes are given as ranges
                if opcode and " to " not in opcode:
                    document.errata.append(
                        Erratum(
                            code="opcode",
                            message=f"Command {name}: opcode is not a value",
                            found=opcode,
                            source=source,
                        )
                    )
                continue
            if name.endswith(" Commands"):
                # A row pointing at the commands of another table, as the
                # range of opcodes the Fabrics commands take
                continue
            command_set.commands[alias(name)] = Command(
                name=name,
                opcode=int(match["hex"], 16),
                columns={
                    k: v
                    for k, v in entry.columns.items()
                    if k not in ("opcode", "command")
                },
                footnotes={
                    "name" if k == "command" else k: v
                    for k, v in entry.marked.items()
                    if k != "opcode"
                },
                source=source,
            )
        return

    if figure.layout is None:
        if figure.entries:
            # Which column has the codes is decided once for the table
            code = code_column(figure.columns, figure.entries)
            named = named_by(figure.columns, code)
            document.values.append(
                Values(
                    kind=subject.kind,
                    name=subject.name,
                    qualifier=subject.qualifier,
                    scope=subject.scope,
                    columns=figure.columns,
                    entries=[entry_of(e, code, named) for e in figure.entries],
                    status_code_type=(
                        STATUS_CODE_TYPES.get(alias(subject.qualifier or ""))
                        if subject.kind == "status_values"
                        else None
                    ),
                    status_scope=(
                        STATUS_SCOPES.get(alias(subject.scope or ""))
                        if subject.kind == "status_values"
                        else None
                    ),
                    source=source,
                )
            )
            document.errata += type_values(document.values[-1])
        else:
            document.diagnostics.append(
                note("figure-not-modelled", f"{cite(source)}: '{figure.caption}'")
            )
        return

    dwords = None
    if (
        subject.kind
        in (
            "command_dword",
            "completion_dword",
            "management_dword",
            "pcie_request_dword",
        )
        and subject.lower is not None
    ):
        dwords = (subject.lower, subject.upper or subject.lower)
    elif subject.kind in POINTERS:
        dwords = POINTERS[subject.kind]

    if dwords and (subject.name or subject.qualifier):
        # A caption can give the acronym of the command after its name. A caption that
        # names a field and no command, for example "Command Dword 11 - CNS Specific
        # Identifier", is keyed by the field, for link_titled_operations().
        name = re.sub(r"\s*\([A-Z0-9]+\)$", "", subject.name or "")
        key = ("cqe:" if subject.kind == "completion_dword" else "") + (
            alias(name) if name else QUALIFIED + alias(subject.qualifier or "")
        )
        fields, errata, unnamed = checked(
            fields_of(figure.layout), 32 * (dwords[1] - dwords[0] + 1), source
        )
        took(document, errata, unnamed, source)
        document.dwords.setdefault(key, []).append(
            Dwords(
                lower=dwords[0],
                upper=dwords[1],
                condition=subject.condition,
                selected_when=comparison_of(subject.condition),
                qualifier=subject.qualifier,
                fields=fields,
                source=source,
            )
        )
        return

    read = fields_of(figure.layout)
    # A register with one row and no name, for example "31:00 RO 0h Shall be cleared to
    # zero" of CCPTR of PCIe 1.4 Figure 23, is that row. The row is named after the
    # register, so that the register has its width.
    if subject.kind == "register" and len(read) == 1 and not read[0].name:
        acronym, _, name = (subject.name or "").partition(" - ")
        read[0].name, read[0].acronym = (name, acronym) if name else (acronym, None)
    fields, errata, unnamed = checked(read, None, source)
    maxima_of(fields, figure.mentions)
    link_counts(fields)
    kind = subject.kind
    # A table whose rows name the structure or the CNS value of each field, for example
    # NVM 1.3 Figure 188, cites fields of other structures.
    if kind == "other" and {"data_structure", "cns_value"} & set(figure.columns):
        kind = "cited_fields"
    # A layout of another kind that starts at byte 0 also lays out a whole structure,
    # for example the entries of SLM 1.3 Figure 13.
    whole = kind in WHOLE or (kind == "other" and starts_at_zero(fields))
    if whole and not (errata or unnamed):
        errata = uncovered(fields, figure.layout.unit, source)
        errata += uncovered_entries(fields, figure.layout.unit, source)
        errata += misnumbered(fields, figure.layout.unit, source)
    errata += shared_acronyms(fields, source)
    took(document, errata, unnamed, source)
    title = subject.name or figure.caption
    hexadecimal = REGEX_HEX.match(subject.offset or "")
    document.structures.append(
        Structure(
            title=title,
            name=title,
            kind=kind,
            unit=figure.layout.unit,
            qualifier=subject.qualifier,
            offset=int(hexadecimal["hex"], 16) if hexadecimal else None,
            fields=fields,
            notes=figure.layout.notes,
            source=source,
        )
    )
    made = document.structures[-1]
    encoded_by_mentions(made.fields, figure.mentions)
    found = extended_by_text(made, figure.mentions, document.structures[:-1])
    if found:
        made.extends, made.extends_field = found


def first_byte(structure: Structure) -> Optional[int]:
    """
    The lowest byte that a field of 'structure' lays out, or None for a layout of bits
    """

    if structure.unit != "bytes":
        return None
    lowers = [f.lower for f in structure.fields if f.kind == "span"]
    return min((low for low in lowers if low is not None), default=None)


def extended_by_text(
    structure: Structure, mentions: List[str], before: List[Structure]
) -> Optional[Tuple[Source, Optional[str]]]:
    """
    The structure among 'before', of the same document, that 'structure' extends where
    the text says so, and the field of that structure that 'structure' lays out.
    'structure' is a layout of bytes that does not start at byte 0. For example, "The
    format of the CPSR field in the Control Primitive Success Response is shown in
    Figure 41" gives the field CPSR of the structure that starts at byte 0 and holds the
    bytes of Figure 41.
    """

    lowest = first_byte(structure)
    if not lowest:
        return None
    upper = max(f.upper or 0 for f in structure.fields if f.kind == "span")
    number = structure.source.figure_nr
    whole = [s for s in before if first_byte(s) == 0]
    for mention in mentions:
        match = re.search(
            r"format of the (?P<acronym>[A-Z][A-Z0-9]+) field\b.* is shown in "
            rf"Figure {number}\b",
            mention,
        )
        if match:
            holding = [
                s
                for s in whole
                for f in s.fields
                if f.acronym == match["acronym"]
                and f.kind == "span"
                and (f.lower or 0) <= lowest
                and (f.upper or 0) >= upper
            ]
            if len(holding) == 1:
                return holding[0].source, match["acronym"]
    return None


FOOTNOTES = r"(?P<footnotes>(?:\s*\d+(?:,\s*\d+)*)?)"
TYPED_FORMS: List[Tuple[TypedKind, re.Pattern]] = [
    ("level", re.compile(r"^(?P<level>M|O|P|NR|R)" + FOOTNOTES + r"$")),
    ("flag", re.compile(r"^(?P<flag>Yes|No|Y|N)" + FOOTNOTES + r"$", re.IGNORECASE)),
    (
        "identifier",
        re.compile(
            # A range may give the "h" once, after its upper bound: "86 to BFh"
            r"^(?:(?P<lower>[0-9A-Fa-f]+)h"
            r"(?:\s*(?:to|-)\s*(?P<upper>[0-9A-Fa-f]+)h)?"
            r"|(?P<bare_lower>[0-9A-Fa-f]+)\s*(?:to|-)\s*(?P<bare_upper>[0-9A-Fa-f]+)h)"
            + FOOTNOTES
            + r"$"
        ),
    ),
    (
        "number",
        re.compile(
            r"^(?P<binary>[01]+)b(?:\s*(?:to|-)\s*(?P<binary_upper>[01]+)b)?"
            + FOOTNOTES
            + r"$"
        ),
    ),
    (
        "identifiers",
        re.compile(r"^[0-9A-Fa-f]+h(?:(?:\s*,)?(?:\s+and)?\s+[0-9A-Fa-f]+h)+$"),
    ),
    (
        "number",
        re.compile(r"^(?P<decimal>\d+)(?:\s*(?:to|-)\s*(?P<decimal_upper>\d+))?$"),
    ),
    ("others", re.compile(r"^All other(?:s| values)?$", re.IGNORECASE)),
    ("note", re.compile(r"^Note\s*(?P<note>\d+)$", re.IGNORECASE)),
    ("reference", re.compile(r"^Refer to (?:the )?(?P<reference>.+?)\.?$")),
    ("reserved", re.compile(r"^Reserved\b.*$", re.IGNORECASE)),
    (
        "vendor_specific",
        re.compile(r"^Vendor Specific" + FOOTNOTES + r"$", re.IGNORECASE),
    ),
    (
        "not_applicable",
        re.compile(r"^(?:n/a|not applicable)" + FOOTNOTES + r"$", re.IGNORECASE),
    ),
]
# The forms any typed column can hold besides its own
COMMON = {"note", "reference", "reserved", "vendor_specific", "not_applicable"}


def typed_of(text: str) -> Optional[Typed]:
    """The typed form of the text of a value, or None when it has none"""

    text, marked = unmarked(text)
    for kind, regex in TYPED_FORMS:
        match = regex.match(text.strip())
        if not match:
            continue
        groups = match.groupdict()
        footnotes = [int(n) for n in re.findall(r"\d+", groups.get("footnotes") or "")]
        typed = Typed(kind=kind, footnotes=marked + footnotes)
        if kind == "level":
            typed.level = groups["level"]
        elif kind == "flag":
            typed.flag = groups["flag"].lower().startswith("y")
        elif kind == "identifier":
            lower, upper = groups["lower"] or groups["bare_lower"], groups["upper"]
            upper = upper or groups["bare_upper"]
            typed.lower = int(lower, 16)
            typed.upper = int(upper, 16) if upper else typed.lower
        elif kind == "number":
            if groups.get("binary"):
                typed.lower = int(groups["binary"], 2)
                upper = groups.get("binary_upper")
                typed.upper = int(upper, 2) if upper else typed.lower
            else:
                typed.lower = int(groups["decimal"])
                upper = groups.get("decimal_upper")
                typed.upper = int(upper) if upper else typed.lower
        elif kind == "identifiers":
            typed.listed = [int(code, 16) for code in re.findall(r"([0-9A-Fa-f]+)h", text)]
        elif kind == "note":
            typed.note = int(groups["note"])
        elif kind == "reference":
            typed.reference = groups["reference"]
        return typed
    return None


def kinds_of(column: str, values: "Values") -> Optional[set]:
    """The kinds of value a column holds, by its name and the table it is of,
    or None for a column of text"""

    if column in ("om", "io", "admin", "administrative", "discovery") or (
        "requirement" in column
    ):
        return {"level"}
    if column.startswith(
        ("persistent", "uses_memory", "namespace_identifier_used", "current_setting")
    ):
        return {"flag"}
    if values.kind == "cns_values" and column in ("nsid", "cntid", "csi"):
        # The base specification says whether the field is used, a command set
        # specification may give the value of it
        return {"flag", "identifier"}
    if column in ("identifier", "cns_value") or (
        column == "value" and "identifier" in values.columns
    ):
        return {"identifier"}
    return None


def column_title(column: str) -> str:
    """
    The title of a column from its key, as a document writes it, for example "I/O" for
    "io"
    """

    return {"io": "I/O", "om": "O/M"}.get(column, column.replace("_", " "))


# A kind of value, as an author reads it
KIND_WORDS = {"flag": "a flag", "identifier": "an identifier", "level": "a level"}


def free_text(values: "Values") -> set:
    """The columns of 'values' that hold sentences in most of their rows, as a
    column of descriptions whose name says "requirement", which are text
    whatever their name"""

    cells: Dict[str, List[str]] = {}
    for entry in values.entries:
        for column, text in {entry.value_column: entry.value, **entry.columns}.items():
            if text.strip():
                cells.setdefault(column, []).append(text)
    return {
        column
        for column, texts in cells.items()
        if sum(len(text.split()) > 4 for text in texts) * 2 > len(texts)
    }


def type_values(values: "Values") -> List["Erratum"]:
    """Type the values of the columns of a known kind of 'values', and the
    errata of those of no form their column holds"""

    errata = []
    prose = free_text(values)
    for entry in values.entries:
        cells = {entry.value_column: entry.value, **entry.columns}
        others = [v for k, v in cells.items() if k != entry.value_column and v]
        for column, text in cells.items():
            kinds = kinds_of(column, values)
            # The value of a row is typed wherever it is a code or a number, in a
            # column of no known kind too, for which text is no erratum
            loose = kinds is None and column == entry.value_column
            if loose:
                kinds = {"identifier", "identifiers", "number", "others"}
            if kinds is None or column in prose or not text.strip():
                continue
            typed = typed_of(text)
            if typed and typed.kind in kinds | COMMON:
                entry.typed[column] = typed
            elif loose:
                continue
            elif others or entry.name or entry.description:
                errata.append(
                    Erratum(
                        code="value",
                        message=(
                            f"'{text}' in the column \"{column_title(column)}\" is "
                            "not " + " or ".join(KIND_WORDS[k] for k in sorted(kinds))
                        ),
                        found=text,
                        source=values.source,
                    )
                )
    return errata


# A code as a table writes it, "01h" or "0010b", a range of codes, as "C0h to
# FFh", or a code an expression goes on from, as an offset counted from the
# first, "1000h + (2 * STRIDE)"
CODE = r"(?:[0-9A-F]+h|[01]+b)"
REGEX_CODE = re.compile(
    rf"^{CODE}(?:\s*\+.*|(?:\s*(?:to|-)\s*{CODE})?" + FOOTNOTES + r")$"
)


def code_column(columns: List[str], entries: List[Dict[str, str]]) -> Optional[str]:
    """The column of 'columns' holding the code of each of 'entries', or None
    of a table without one

    A column holds codes where more than half of the entries have a code in
    it, and its other cells are left open, as "N/A" or "Reserved". The code of
    an entry is no other entry's: the column is the one whose header says it
    combines the codes of the others, as "Combined Opcode", where it has no
    code twice; else the first column of codes, where no column of codes has
    a code twice. Codes that repeat, as flags or the major and minor parts of
    a version, say something of an entry, not which it is."""

    holding: Dict[str, List[str]] = {}
    for column in columns:
        texts = [entry[column] for entry in entries if entry.get(column)]
        codes = [text for text in texts if REGEX_CODE.match(text)]
        if 2 * len(codes) > len(entries) and all(
            (typed := typed_of(text)) is not None and typed.kind in COMMON
            for text in texts
            if not REGEX_CODE.match(text)
        ):
            holding[column] = codes
    once = [c for c, codes in holding.items() if len(set(codes)) == len(codes)]
    combined = [c for c in once if c == "opcode" or c.startswith("combined_")]
    if combined:
        return combined[0]
    return once[0] if once and len(once) == len(holding) else None


def named_by(columns: List[str], code: Optional[str]) -> Optional[str]:
    """The column of 'columns' naming what the column 'code' has the code of,
    where no column is a name by its header: the command, else the first
    column, which is what the table lists"""

    if code is None or any(c == "name" or c.endswith("_name") for c in columns):
        return None
    if "command" in columns:
        return "command"
    return columns[0] if columns[0] != code else None


def entry_of(
    entry: Dict[str, str], code: Optional[str] = None, named: Optional[str] = None
) -> Entry:
    """An entry by its value, whichever column holds it: one that is a value
    by its header, else 'code', the column of the table's codes, else the
    command or the name, else the first. An entry with no name column takes
    its name from the column 'named' when another column holds its value,
    for example "Directive" in the table of "Directive" and "Directive Type
    Value"."""

    keys = ("value", "cns_value", "identifier")
    by_header = next(
        (k for k in keys if entry.get(k)),
        next((k for k in entry if k.endswith("_value") and entry[k]), ""),
    )
    others = [k for k in (code or "", "command", "name") if entry.get(k)]
    key = by_header or next(iter(others), next(iter(entry), ""))
    names = [k for k in entry if k == "name" or (k.endswith("_name") and k != key)]
    name_key = next((k for k in names if entry.get(k)), None)
    if (
        name_key is None
        and named not in (key, "description")
        and entry.get(named or "")
    ):
        name_key = named
    # The footnote markers of the value, the name, the description and the other
    # columns, in that order, are the footnotes of the entry.
    marked: Dict[str, List[int]] = {}

    def plain(column: str, within: bool = True, mark: str = "") -> str:
        text, numbers = unmarked(entry.get(column, ""), within)
        if numbers:
            marked[mark or column] = numbers
        return text

    value = plain(key)
    name = plain(name_key, mark="name") if name_key else None
    description, footnotes = footnoted(entry.get("description", ""))
    if footnotes:
        marked["description"] = footnotes
    columns = {k: plain(k) for k in entry if k not in (key, name_key, "description")}
    return Entry(
        value=value,
        value_column=key,
        name=name,
        description=description,
        footnotes=list(dict.fromkeys(n for ns in marked.values() for n in ns)),
        marked=marked,
        columns=columns,
    )


PLACE_KINDS: Dict[str, Role] = {
    "reserved": "reserved",
    "vendor_specific": "vendor_specific",
}


def role_of(entry: Entry) -> Role:
    """
    What 'entry' is: the place its name, else its value, else the start of its
    description says it holds, as "Reserved", or else "field"
    """

    typed = entry.typed.get(entry.value_column)
    if entry.name:
        return senfd.fields.place_of(entry.name) or "field"
    if typed and typed.kind in PLACE_KINDS:
        return PLACE_KINDS[typed.kind]
    if entry.description:
        first = re.split(r"[.:]", entry.description.split("\n")[0], maxsplit=1)[0]
        return senfd.fields.place_of(first.strip()) or "field"
    return "field"


def entries_of(document: SpecDocument) -> Iterator[Entry]:
    """Every entry of the tables of values and of the values of fields of 'document'"""

    for values in document.values:
        yield from values.entries
    for _, fields in laid_out(document):
        for field in fields_within(fields):
            yield from field.values
            for case in field.cases:
                yield from case.values


def give_roles(document: SpecDocument) -> None:
    """Give every entry of 'document' the role that role_of() finds"""

    for entry in entries_of(document):
        entry.role = role_of(entry)


def add_dwords(have: List[Dwords], dwords: Dwords) -> None:
    """
    Add 'dwords' to 'have', unless they are there already; two figures
    describing the same dwords, as the base specification and a command set
    specification do, are both kept, each saying where it is from
    """

    if all(d.source != dwords.source for d in have):
        have.append(dwords)


def initials(name: str) -> str:
    """The initials of the words of 'name', as "hctm" of "Host Controlled
    Thermal Management" """

    return "".join(word[0] for word in re.findall(r"[A-Za-z0-9]+", name)).lower()


def names_match(caption: str, name: str) -> bool:
    """
    Whether a caption names the thing of 'name': by the same name, by the
    initials of either, or by a longer name starting with it, as "Arbitration &
    Command Processing" is the feature "Arbitration"; a caption shorter than the
    name, as "Foo" of "Foo Config", names something else
    """

    a, b = alias(caption), alias(name)
    if not a or not b:
        return False
    return (
        a == b
        or a == initials(name)
        or b == initials(caption)
        or a.startswith(b + "_")
        or abbreviates(a.split("_"), b.split("_"))
    )


def abbreviates(short: List[str], long: List[str]) -> bool:
    """
    Whether the words 'short' abbreviate the words 'long', each word of 'short'
    being a word of 'long', the initials of the next words of 'long', as "fdp"
    of "flexible data placement", or the start of the next word, as "config"
    of "configuration"
    """

    if not short:
        return not long
    if not long:
        return False
    word, rest = short[0], short[1:]
    if word == long[0] or (len(word) >= 4 and long[0].startswith(word)):
        if abbreviates(rest, long[1:]):
            return True
    for n in range(2, len(long) + 1):
        if word == "".join(w[0] for w in long[:n]) and abbreviates(rest, long[n:]):
            return True
    return False


def marked_of(entry: Entry) -> Dict[str, List[int]]:
    """
    The footnotes marked on the name and the other columns of 'entry', by the key of the
    column, with the key "name" for the name. An entry without a name has the markers of
    its description under "name".
    """

    return {
        "name" if k == "description" and not entry.name else k: v
        for k, v in entry.marked.items()
        if k != entry.value_column
    }


def identified(document: SpecDocument, name_column: str, kind: str):
    """
    The identifier, name and other columns of each entry of the tables of
    identifiers that have the column 'name_column', or whose caption is of
    'kind', with the source of the table; the tables of requirements list the
    identifiers too
    """

    for values in document.values:
        if not (
            values.kind == kind or {"identifier", name_column} <= set(values.columns)
        ):
            continue
        for entry in values.entries:
            match = REGEX_HEX.match(without_footnote(entry.value))
            name = without_footnote(entry.name or entry.description or "")
            if match and name:
                yield int(match["hex"], 16), name, entry, values.source


REGEX_FEATURE_SECTION = re.compile(r"(?:\(Feature Identifier [0-9A-F]+h\)(?:,\s*)?)+$")


def feature_identifiers(dwords: "Dwords") -> List[int]:
    """The feature identifiers that end the title of the section of
    'dwords', as 7Dh, 7Eh and 7Fh of "Host Metadata (Feature Identifier
    7Dh), (Feature Identifier 7Eh), (Feature Identifier 7Fh)" """

    match = REGEX_FEATURE_SECTION.search(dwords.source.section_title or "")
    return [int(h, 16) for h in re.findall(r"([0-9A-F]+)h", match[0])] if match else []


def placed_key(key: str, dwords: "Dwords") -> Tuple[str, str, int]:
    """What 'used' holds of one figure of dwords under 'key' that is placed
    while others under the key are not"""

    return (key, dwords.source.document, dwords.source.figure_nr)


def unassigned_of(
    dwords: Dict[str, List["Dwords"]], used: set
) -> Dict[str, List["Dwords"]]:
    """The dwords of each key that 'used' says nothing has taken: neither the
    key nor the figure of the dwords"""

    unassigned = {}
    for key, described in dwords.items():
        if key in used:
            continue
        left = [d for d in described if placed_key(key, d) not in used]
        if left:
            unassigned[key] = left
    return unassigned


def link_features(document: SpecDocument, used: set) -> None:
    """The features of the feature identifier tables, one by identifier, with
    the dwords described for each, which the captions name by the feature"""

    seen: Dict[int, str] = {}
    for identifier, name, entry, source in identified(
        document, "feature_name", "feature_identifiers"
    ):
        if identifier in seen:
            continue
        seen[identifier] = alias(name)
        document.features[alias(name)] = Feature(
            identifier=identifier,
            name=name,
            columns=entry.columns,
            footnotes=marked_of(entry),
            source=source,
        )

    # The section a figure is in names the feature, where its title gives the
    # identifier, as "Flexible Data Placement Events (Feature Identifier 1Eh)";
    # the captions there may name another feature or none
    by_identifier = {f.identifier: f for f in document.features.values()}
    left: Dict[str, List[Dwords]] = {}
    for key, described in document.dwords.items():
        if key in used:
            continue
        cqe = key.startswith("cqe:")
        left[key] = []
        for dwords in described:
            if placed_key(key, dwords) in used:
                continue
            features = [
                by_identifier[i]
                for i in feature_identifiers(dwords)
                if i in by_identifier
            ]
            if not features:
                left[key].append(dwords)
                continue
            for feature in features:
                add_dwords(feature.cqe if cqe else feature.sqe, dwords)
            used.add(placed_key(key, dwords))
        if not left[key]:
            used.add(key)
            del left[key]

    # The exact name first, then the looser matches, so that "Asynchronous
    # Event Configuration" is not taken by a feature it merely starts with
    for exact in (True, False):
        for key, described in left.items():
            if key in used:
                continue
            cqe = key.startswith("cqe:")
            caption = key.removeprefix("cqe:")
            for feature in document.features.values():
                if (
                    (alias(feature.name) == caption)
                    if exact
                    else names_match(caption, feature.name)
                ):
                    for dwords in described:
                        add_dwords(feature.cqe if cqe else feature.sqe, dwords)
                    used.add(key)
                    break
    for feature in document.features.values():
        for described in (feature.sqe, feature.cqe):
            described.sort(key=lambda d: (d.source.document, d.source.figure_nr))


def log_page_key(name: str) -> str:
    """The name of a log page without what captions and tables add to it:
    "Get Log Page - ", " Log Page", " Log Entry", a scope in parentheses"""

    name = re.sub(r"^Get Log Page - ", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s*\([^)]*\)$", "", name)
    name = re.sub(r"\s+Log(?: Page)?(?: Entry)?$", "", name, flags=re.IGNORECASE)
    return alias(name)


def link_log_pages(document: SpecDocument) -> None:
    """
    The log pages of the tables of log page identifiers, one for each identifier, each
    with the structure that lays it out. The first table of log page identifiers that
    lists a log page gives its name, for example Base 2.4 Figure 209. The tables of
    requirements come after it, and they can list a log page once for each scope, for
    example "SMART / Health Information (Controller scope)" and "(Namespace scope)" of
    Figure 31. The columns of the later tables, such as the requirements, are added to
    the log page.

    The structure of a log page is the figure in the section that its row cites whose
    name is a name that a table gives the log page. Otherwise it is the first figure of
    a log page in that section, and otherwise the first figure of a data structure
    there, for example Figure 270, "Feature Identifiers Effects", for 12h. Where the row
    cites no section, the structure is the one with the name of the log page.
    """

    candidates = sorted(
        (s for s in document.structures if s.kind in ("log_page", "data_structure")),
        key=lambda s: (s.kind != "log_page", s.source.document, s.source.figure_nr),
    )

    def cited(entry: Entry, source: Source) -> List[Structure]:
        number = entry.columns.get("reference", "").strip()
        if not REGEX_SECTION_NUMBER.match(number):
            return []
        return [
            s
            for s in candidates
            if s.source.document == source.document
            and s.source.section is not None
            and (s.source.section + ".").startswith(number + ".")
        ]

    found = list(identified(document, "log_page_name", "log_page_identifiers"))
    # The tables of identifiers come first, each in the order of the documents.
    kinds = {(v.source.document, v.source.figure_nr): v.kind for v in document.values}
    found.sort(
        key=lambda f: kinds.get((f[3].document, f[3].figure_nr))
        != "log_page_identifiers"
    )
    # The names that each table gives each identifier
    names: Dict[int, List[str]] = {}
    for identifier, name, _, _ in found:
        names.setdefault(identifier, []).append(log_page_key(name))
    taken = {page.identifier: page for page in document.log_pages.values()}
    for identifier, name, entry, source in found:
        if identifier in taken:
            # A later table adds its columns, for example the requirements of Figure 31.
            page = taken[identifier]
            if (
                log_page_key(name) != log_page_key(page.name)
                and name not in page.aliases
            ):
                page.aliases.append(name)
            for key, text in entry.columns.items():
                page.columns.setdefault(key, text)
            for key, numbers in marked_of(entry).items():
                if key != "name" and key not in page.footnotes:
                    page.footnotes[key] = numbers
            continue
        wanted = log_page_key(name)
        # Of several figures in the section, for example "Extended Discovery" and
        # "Discovery" of Base 2.4 Figures 321 and 322, the structure is the figure whose
        # name is a name that a table gives the log page.
        section = cited(entry, source)
        named = [s for s in section if log_page_key(s.title) in names[identifier]]
        structure = (
            next(iter(named + section), None)
            or next((s for s in candidates if log_page_key(s.title) == wanted), None)
            or next(
                (s for s in candidates if names_match(log_page_key(s.title), wanted)),
                None,
            )
        )
        # Two log pages with one name and two scopes are each keyed by the name and the
        # scope.
        key = wanted
        if key in document.log_pages:
            key = alias(re.sub(r"\s+Log Page$", "", name, flags=re.IGNORECASE))
        taken[identifier] = document.log_pages[key] = LogPage(
            identifier=identifier,
            name=name,
            columns=dict(entry.columns),
            footnotes=marked_of(entry),
            structure=structure,
            source=source,
        )


def link_directives(document: SpecDocument, used: set) -> None:
    """
    The operations of each directive, from the tables of a directive's
    operations, as operations of the commands sending and receiving them; an
    operation has the dwords its caption names it by, and the structures named
    after the directive and the operation
    """

    types: Dict[str, int] = {}
    for values in document.values:
        if not {"directive", "directive_type_value"} <= set(values.columns):
            continue
        for entry in values.entries:
            match = REGEX_HEX.match(entry.value)
            name = entry.name or ""
            if match and name:
                types[alias(name)] = int(match["hex"], 16)

    commands: Dict[str, List[Command]] = {}
    for command_set in document.command_sets.values():
        for key, command in command_set.commands.items():
            commands.setdefault(key, []).append(command)

    for values in document.values:
        if "directive_operation_value" not in values.columns:
            continue
        # "Streams - Directive Operations", "Identify Directive - ..."
        directive = re.sub(
            r"(?:\s+Directive)?\s+-\s+Directive Operations$", "", values.name or ""
        )
        dtype = types.get(alias(directive))
        for entry in values.entries:
            match = REGEX_HEX.match(entry.value)
            name = entry.name or ""
            sending = entry.columns.get("directive_command", "")
            if not match or not name or not sending:
                continue
            selectors = {"DOPER": int(match["hex"], 16)}
            if dtype is not None:
                selectors = {"DTYPE": dtype, **selectors}
            operation = Operation(
                name=name,
                selectors=selectors,
                structures=[
                    s.title
                    for s in document.structures
                    if alias(s.title).startswith(alias(directive))
                    and alias(name) in alias(s.title)
                ],
                source=values.source,
            )
            for key, have in (
                (alias(name), operation.sqe),
                (f"cqe:{alias(name)}", operation.cqe),
            ):
                for dwords in document.dwords.get(key, []):
                    add_dwords(have, dwords)
                if key in document.dwords:
                    used.add(key)
            for command in commands.get(alias(sending), []):
                command.operations.append(operation)


def gaps(command: Command) -> List[Erratum]:
    """
    The bits of a command's dwords that no figure gives a field, all its
    figures of the dwords taken together, as the base specification and a
    command set's give a dword's fields between them; a figure of a condition
    is taken with those of none
    """

    errata = []
    for kind, described in (("cdw", command.sqe), ("cqe dw", command.cqe)):
        spans = {(d.lower, d.upper) for d in described}
        for lower, upper in sorted(spans):
            figures = [d for d in described if (d.lower, d.upper) == (lower, upper)]
            plain = [d for d in figures if d.condition is None]
            named = sorted(d.condition for d in figures if d.condition)
            conditions: List[Optional[str]] = list(dict.fromkeys(named)) or [None]
            for condition in conditions:
                these = plain + [d for d in figures if d.condition == condition]
                fields = [f for d in these for f in d.fields]
                if any(f.lower is None or f.unit != "bits" for f in fields):
                    continue
                width = 32 * (upper - lower + 1)
                covered = {
                    b
                    for f in fields
                    if f.lower is not None and f.upper is not None
                    for b in range(f.lower, f.upper + 1)
                }
                missing = sorted(set(range(width)) - covered)
                if not missing:
                    continue
                span = f"{kind}{lower}" if lower == upper else f"{kind}{lower}-{upper}"
                if condition:
                    span += f" if {condition}"
                errata.append(
                    Erratum(
                        code="gap",
                        message=(
                            f"{command.name} {span}: bits "
                            + (
                                f"{missing[0]} to {missing[-1]}"
                                if len(missing) > 1
                                else f"{missing[0]}"
                            )
                            + " are of no field"
                        ),
                        found=", ".join(str(b) for b in missing[:8]),
                        source=these[0].source,
                    )
                )
    return errata


# Text that lists codes, for example "10h and 11h" of LBARS in NVM 1.3 Figure 140,
# refers to other values and names none.
REGEX_CODES = re.compile(
    r"^(?:[0-9A-F]+[hb](?:(?:,|,? and|,? or| to) [0-9A-F]+[hb])*"
    r"|(?i:all|all other(?:s| values)?))$"
)


def value_names(entry: "Entry") -> List[str]:
    """
    The name of a value of a field, as a list of none or one name. The name is the name
    of the entry, and otherwise the text of the first column that names the value, for
    example the column "power_scope" for CPS of Base 2.4 Figure 36. An aside of prose
    and a closing period are removed, for example from "Domain scope (i.e., the NVM
    subsystem supports multiple domains ...". The heading that the value is under does
    not name the value. Nor does a column that lists other codes, for example "1h" or
    "All other values" of SGLDST in Base 2.4 Figure 118.
    """

    if entry.name:
        return [entry.name]
    skip = {"reference", "om", "description", "refer_to_section", "section"}
    listing = False
    for column, text in entry.columns.items():
        if column in skip or not text:
            continue
        name = name_of_cell(text)
        if REGEX_CODES.match(name):
            listing = True
            continue
        if typed_of(text):
            continue
        # After a column that lists codes, only a cell that holds a name and its
        # definition gives a name, for example "Address" of "Address: The Address field
        # specifies ..." of SGLDST 0h in Base 2.4 Figure 118.
        if listing and ": " not in " ".join(text.split()):
            return []
        # A sentence that says what a field holds defines the value and does not name
        # it, for example "This field contains the Controller Identifier ..." of CTRLID
        # 02h in MI 2.2 Figure 112.
        if re.match(r"(?:This|The) ", name) and len(name.split()) > 6:
            return []
        return [name]
    return []


def is_aside(text: str, name: str) -> bool:
    """
    Whether 'text', in a parenthesis after 'name', is an aside to the name rather than
    part of it. Prose is an aside, for example "i.e., ..." or "no shutdown has been
    requested", and text with two words in lower case is prose. After a name of words, a
    detail of numbers and symbols is an aside, for example "802.3 + TCP/IP" after
    NVMe/TCP in Boot 1.4 Figure 8. "Controller scope" and "Optional" qualify the name
    and are part of it. "(2 * (4 << CAP.DSTRD))" after "03h +" is part of a formula.
    """

    return (
        text.startswith(("i.e.,", "e.g.,", "refer to"))
        or sum(w[:1].islower() for w in re.split(r"[\s/]+", text)) >= 2
        or bool(
            re.search(r"\d|\+", text)
            and re.fullmatch(r"[A-Za-z][\w/-]*(?: [A-Za-z][\w/-]*)*", name)
        )
    )


def name_of_cell(text: str) -> str:
    """
    The name in the text of a cell that names a value. Where the cell holds a name and
    its definition, the name is the text before the colon, for example "Single Command
    Cancel" of ACODE 00b of Base 2.4 Figure 647. A parenthesis of prose after the name
    is removed, whether or not it is closed, for example "(i.e., ...". A closing period
    is removed, and so is an acronym after the name, for example "(CTemp)" of "Composite
    Temperature (CTemp)" of MI 2.2 Figure 199.
    """

    text = " ".join(text.split())
    head, colon, _ = text.partition(": ")
    if colon and len(head.split()) <= 6:
        text = head
    name, paren, aside = text.partition(" (")
    if paren and is_aside(aside, name):
        text = name
    text = re.sub(
        r" \((?=[A-Za-z0-9]*[A-Z][A-Za-z0-9]*[A-Z])[A-Z][A-Za-z0-9]+\)$",
        "",
        text.removesuffix("."),
    )
    return text


def names_operation(caption: str, name: str) -> bool:
    """Whether a caption names the operation of 'name': by that name, or that
    name with only "Operation" or "Management Operation" after it; "Create
    Controller Data Queue" is not the operation Create"""

    a, b = alias(caption), alias(name)
    return bool(b) and a in (b, f"{b}_operation", f"{b}_management_operation")


def shared_prefix(a: Optional[str], b: Optional[str]) -> int:
    """How many leading parts the section numbers 'a' and 'b' share"""

    n = 0
    for x, y in zip((a or "").split("."), (b or "").split(".")):
        if x != y or not x:
            break
        n += 1
    return n


def link_operations(document: SpecDocument, used: set) -> None:
    """
    The operations of the commands a field of whose dwords selects, by the
    values the field takes: a value whose name names dwords described for it,
    as "Suspend - Command Dword 11" of the value Suspend of the Select field of
    Migration Send, or names the section they are in, is an operation of the
    command with those dwords

    Only dwords of the document describing the selecting field are taken, and
    dwords the values of two commands name are those of the command whose
    section is nearest theirs; where that does not decide, they are a
    diagnostic, and neither command's.
    """

    def named(described: Dwords, name: str, key: str) -> bool:
        title = re.sub(r"\s*\([^)]*\)$", "", described.source.section_title or "")
        return names_operation(key.removeprefix("cqe:"), name) or (
            bool(title) and alias(title) == alias(name)
        )

    Claim = Tuple[Command, Bits, Entry, str, Dwords]
    claims: Dict[int, List[Claim]] = {}
    described_by: Dict[int, Tuple[str, Dwords]] = {}
    for command_set in document.command_sets.values():
        for command in command_set.commands.values():
            for selecting in list(command.sqe):
                for field in selecting.fields:
                    for value in field.values:
                        typed = value.typed.get(value.value_column)
                        if (
                            typed is None
                            or typed.lower is None
                            or typed.lower != typed.upper
                        ):
                            continue
                        for name in value_names(value):
                            for key, listed in document.dwords.items():
                                if key in used:
                                    continue
                                for d in listed:
                                    if d.source.document != selecting.source.document:
                                        continue
                                    if named(d, name, key):
                                        claims.setdefault(id(d), []).append(
                                            (command, field, value, name, selecting)
                                        )
                                        described_by[id(d)] = (key, d)

    for ident, all_claimed in claims.items():
        key, described = described_by[ident]
        claimed = all_claimed
        if len({id(c[0]) for c in claimed}) > 1:

            def nearness(
                claim: Claim, section: Optional[str] = described.source.section
            ) -> int:
                return shared_prefix(claim[4].source.section, section)

            nearest = max(nearness(c) for c in claimed)
            claimed = [c for c in claimed if nearness(c) == nearest]
            if len({id(c[0]) for c in claimed}) > 1:
                document.diagnostics.append(
                    warning(
                        "operation-ambiguous",
                        f"Dwords of '{key}', {described.source.document} figure "
                        f"{described.source.figure_nr}, named by values of "
                        + ", ".join(sorted({c[0].name for c in claimed})),
                    )
                )
                continue
        command, field, value, name, selecting = claimed[0]
        typed = value.typed[value.value_column]
        operation = next((o for o in command.operations if o.name == name), None)
        if operation is None:
            operation = Operation(
                name=name,
                selectors={field.acronym or field.name or "": typed.lower or 0},
                source=selecting.source,
            )
            command.operations.append(operation)
        add_dwords(
            operation.cqe if key.startswith("cqe:") else operation.sqe, described
        )
        used.add(key)


QUALIFIED = "field:"


def names_the_field(named: str, field: Bits) -> bool:
    """
    Whether 'named', the key that a caption gives a field, for example
    "cns_specific_identifiers", names 'field', for example CNS Specific Identifier. The
    key names the field by its name, also in the plural. A key that ends in "field"
    names the field by the start of its name: "log_specific_field" of Base 2.4 Figure
    301 names Log Specific Parameter.
    """

    own = alias(field.name or "")
    stem = re.sub(r"_fields?$", "", named)
    return bool(own) and (
        own in (named, named.removesuffix("s"))
        or (stem != named and own.startswith(stem + "_"))
    )


REGEX_TITLE_CODES = re.compile(
    r"\((?:(?P<label>[A-Za-z][\w /-]*?) )?(?P<code>[0-9A-F]+h)(?P<more>(?:, [^)]*)?)\)$"
)


def link_titled_operations(document: SpecDocument, used: set) -> None:
    """
    The operations of a command or a feature that the titles of sections select by a
    code of a field of its dwords. The title names the field, for example "Lockdown
    Persistence Personality (Personality Identifier 02h)" names PERID of Configurable
    Device Personality, and "SMBus/I2C Frequency (Configuration Identifier 01h)" names
    the Configuration Identifier of Configuration Get of MI 2.2. A title can also name a
    column that names the values of the field, for example "(Management Operation 05h)"
    for SEL. The dwords of no command, in a section with such a title below the section
    of the command, are the dwords of the operation of that name, selected by that code.
    A section below the sections of several commands belongs to the nearest command.

    Dwords whose caption names a field of a command rather than the command are the
    dwords of an operation of the command with that field, in any document. For example,
    "Command Dword 11 - CNS Specific Identifier" of Base 2.4 Figure 343, in "NVM Set
    List (CNS 04h)", is an operation of Identify, whose field is CNSSID. A title that
    gives more codes, for example "(CNS 0Ah, CSI 01h)", selects by each code. A title
    that gives a code alone, for example "Endurance Group List (19h)", selects by the
    field that the other titles of those dwords name.
    """

    def by(fields: List[Bits], label: str) -> Optional[Bits]:
        for field in fields:
            if alias(label) in (alias(field.name or ""), alias(field.acronym or "")):
                return field
        # A field whose values a column names, where the header of the column is the
        # label, for example SEL of Manage Exported NVM Subsystem Receive and the column
        # "Management Operation"
        for field in fields:
            if any(alias(label) in value.columns for value in field.values):
                return field
        return None

    commands: List[Union[Command, Feature]] = [
        command
        for command_set in document.command_sets.values()
        for command in command_set.commands.values()
        if command.sqe
    ]
    commands += [feature for feature in document.features.values() if feature.sqe]
    for key, listed in document.dwords.items():
        if key in used:
            continue
        qualified = key.removeprefix("cqe:").startswith(QUALIFIED)
        named = alias(key.removeprefix("cqe:").removeprefix(QUALIFIED))
        titles = [
            REGEX_TITLE_CODES.search(d.source.section_title or "") for d in listed
        ]
        labels = [m["label"] for m in titles if m and m["label"]]
        common = max(set(labels), key=labels.count) if labels else None
        taken = 0
        for described, match in zip(listed, titles):
            label = match and (match["label"] or (common if qualified else None))
            if not match or not label or label == "Feature Identifier":
                continue
            section = described.source.section or ""
            found = []
            for command in commands:
                fields = [f for d in command.sqe for f in d.fields]
                own = command.sqe[0].source
                if qualified:
                    if not any(names_the_field(named, f) for f in fields):
                        continue
                elif (
                    own.document != described.source.document
                    or not section.startswith(f"{own.section}.")
                ):
                    continue
                selecting = by(fields, label)
                if selecting:
                    found.append((len(own.section or ""), command, selecting))
            if not qualified and found:
                nearest = max(f[0] for f in found)
                found = [f for f in found if f[0] == nearest]
            if len({id(f[1]) for f in found}) != 1:
                continue
            _, command, selecting = found[0]
            selectors = {
                selecting.acronym or selecting.name or "": code_value(match["code"])
            }
            fields = [f for d in command.sqe for f in d.fields]
            for more in re.findall(
                r", ([A-Za-z][\w /-]*?) ([0-9A-F]+h)", match["more"]
            ):
                other = by(fields, more[0])
                if other:
                    selectors[other.acronym or other.name or ""] = code_value(more[1])
            name = REGEX_TITLE_CODES.sub("", described.source.section_title or "")
            name = name.strip()
            operation = next(
                (
                    o
                    for o in command.operations
                    if o.name == name and o.selectors == selectors
                ),
                None,
            )
            if operation is None:
                operation = Operation(
                    name=name, selectors=selectors, source=described.source
                )
                command.operations.append(operation)
            add_dwords(
                operation.cqe if key.startswith("cqe:") else operation.sqe, described
            )
            taken += 1
        if taken == len(listed):
            used.add(key)


def laid_out(document: SpecDocument) -> Iterator[Tuple[Source, List[Bits]]]:
    """The source and the fields of every figure of 'document' that lays out
    fields: the dwords of the commands, and the structures"""

    for described in document.dwords.values():
        for dwords in described:
            yield dwords.source, dwords.fields
    for structure in document.structures:
        yield structure.source, structure.fields


def fields_within(fields: List[Bits]) -> Iterator[Bits]:
    """'fields' and all their subfields, including those of their cases,
    each field before its subfields"""

    for field in fields:
        yield field
        yield from fields_within(field.fields)
        for case in field.cases:
            yield from fields_within(case.fields)


REGEX_FIGURE = re.compile(r"\bFigure\s+(\d+)")
REGEX_SECTION = re.compile(r"\bsection\s+(\d+(?:\.\d+)+)\b")
# A parenthesis giving an example, with the parentheses nested in it
REGEX_EXAMPLE = re.compile(r"\(e\.g\.,(?:[^()]|\([^()]*\))*\)")
# Words of a caption that mark a table of values without naming its field
VALUES_WORDS = {"value", "code", "definition", "encoding", "list"}


def name_words(name: Optional[str]) -> set:
    """The words of 'name' other than VALUES_WORDS, each in the singular, so
    that "Directive Types" and "Directive Type" give the same words"""

    words = [re.sub(r"(?<=..[^s])s$", "", w) for w in alias(name or "").split("_")]
    return {w for w in words if w and w not in VALUES_WORDS}


def names_field(values: Values, field: Bits) -> bool:
    """
    Whether the table 'values' is named for 'field'. It is when the header of
    its value column is the name or the acronym of the field, for example
    "CNS Value" for CNS; when its kind matches the field, for example the log
    page identifiers for Log Page Identifier; or when the words of its
    caption are a subset or a superset of the words of the field's name, for
    example "Directive Types" for Directive Type and "Power Scale" for Power
    Threshold Scale.
    """

    names = {alias(name) for name in (field.name, field.acronym) if name}
    column = values.entries[0].value_column if values.entries else ""
    if column.removesuffix("_value") in names or values.kind.removesuffix("s") in names:
        return True
    caption, name = name_words(values.name), name_words(field.name)
    return bool(caption and name) and (caption <= name or name <= caption)


def holds_values_of(values: Values, field: Bits) -> bool:
    """Whether the entries of 'values' can be values of 'field': more than
    half of the entries have a code, and every code fits in the field"""

    bits = (field.width or 0) * (8 if field.unit == "bytes" else 1)
    codes = [
        typed
        for typed in (typed_of(entry.value) for entry in values.entries)
        if typed is not None and typed.kind in ("identifier", "number")
    ]
    return 2 * len(codes) > len(values.entries) and all(
        (typed.upper or 0) < 2**bits for typed in codes
    )


def link_values(document: SpecDocument) -> None:
    """
    Set 'values_in' on each field that lists no values itself and whose
    description refers to the figure of a table of values in the same
    document, for example CNS of Identify, "Refer to Figure 336". Of the
    tables referred to, the field is linked to the one table whose entries
    can be values of the field and that is named for the field. The
    description of CSI of Identify, for example, refers to both the CNS
    values and the Command Set Identifiers, and only the second is named for
    CSI.
    """

    tables = {(v.source.document, v.source.figure_nr): v for v in document.values}
    for source, fields in laid_out(document):
        for field in fields_within(fields):
            field.values_in = None
            if field.role != "field" or field.values or field.fields:
                continue
            named = [
                tables[(source.document, int(number))]
                for number in dict.fromkeys(REGEX_FIGURE.findall(field.description))
                if (source.document, int(number)) in tables
            ]
            found = [
                values
                for values in named
                if holds_values_of(values, field) and names_field(values, field)
            ]
            if len(found) == 1:
                field.values_in = found[0].source


def bits_wide(structure: Structure) -> Optional[int]:
    """The width of 'structure' in bits, or None where a field of it has no
    upper bound"""

    if not structure.fields or any(f.upper is None for f in structure.fields):
        return None
    upper = max(f.upper or 0 for f in structure.fields)
    return (upper + 1) * (8 if structure.unit == "bytes" else 1)


REGEX_VALUE_OF = re.compile(
    r"value (?:as reported in|of) the (?P<field>[A-Za-z0-9 -]+?)"
    r"(?: \((?P<acronym>[A-Z0-9]+)\))? field (?:of|in) the "
    r"(?P<structure>[A-Za-z0-9 /-]+?) data structure"
)


# A field that holds bytes of another field, for example NQNID of Base 2.4 Figure 698,
# "bytes 223:4 of the NVM Subsystem NVMe Qualified Name (SUBNQN) field (refer to Figure
# 338 )"
REGEX_BYTES_OF = re.compile(
    r"contain bytes \d+:\d+ of the [A-Za-z0-9 -]+? \((?P<acronym>[A-Z0-9]+)\) "
    r"field \(refer to Figure (?P<figure>\d+) ?\)"
)


def all_fields(fields: List[Bits]) -> Iterator[Bits]:
    """Each field of 'fields' and, depth first, the fields within it"""

    for field in fields:
        yield field
        yield from all_fields(field.fields)


REGEX_MENTIONED_ENCODING = re.compile(
    r"\bThe (?P<term>[a-z][\w ]*?) is (?:indicated|reported|encoded) as an? "
    r"(?P<encoding>ASCII|UTF-8) (?:null-terminated )?string\b"
)


def encoded_by_mentions(fields: List[Bits], mentions: List[str]) -> None:
    """
    Set the encoding of each field that has none and whose name begins with a term that
    a paragraph referring to its figure calls a string. For example, "The firmware
    revision is indicated as an ASCII string", of Base 2.4 Figure 215, gives FRS1 to
    FRS7, "Firmware Revision for Slot 1" and so on, the encoding "ascii".
    """

    for mention in mentions:
        for match in REGEX_MENTIONED_ENCODING.finditer(" ".join(mention.split())):
            term = match["term"].casefold()
            encoding: Literal["ascii", "utf-8"] = (
                "ascii" if match["encoding"] == "ASCII" else "utf-8"
            )
            for field in all_fields(fields):
                if not field.encoding and (field.name or "").casefold().startswith(
                    term
                ):
                    field.encoding = encoding


def is_nqn(field: Bits) -> bool:
    """
    Whether 'field' holds an NVMe Qualified Name: its acronym ends in NQN and it is at
    least 64 bytes, for example SUBNQN and AVENQN
    """

    return bool(
        field.acronym
        and field.acronym.endswith("NQN")
        and field.unit == "bytes"
        and (field.width or 0) >= 64
    )


def link_encodings(document: SpecDocument) -> None:
    """
    Set the encoding and the byte order of each field that has none from another field.
    A field whose description says that it has the value of another field takes the
    encoding and the byte order of that field. For example, FR of NVM 1.3 Figure 189,
    "the value of the FR field in the Identify Controller data structure", is "ascii",
    as FR of Base 2.4 Figure 338 is. Where more than one structure of that name has the
    field, the encoding is taken where they all give the same.

    A field that holds an NQN takes the encoding of the NQN fields that state one, as
    SUBNQN of Base 2.4 Figure 338 does. A field takes the byte order or the encoding of
    the fields of the same name, acronym and width in other documents that state it,
    where those fields agree. For example, NGUID and EUI64 of KV 1.4 Figure 42, which
    refer to the Base specification, are big-endian as in NVM 1.3 Figure 123. A field
    that holds bytes of another field takes the encoding of that field, as NQNID of Base
    2.4 Figure 698 takes the encoding of SUBNQN of Figure 338. Each taken encoding and
    byte order names the figure it comes from.
    """

    for structure in document.structures:
        for field in all_fields(structure.fields):
            if field.encoding and field.byte_order:
                continue
            match = REGEX_VALUE_OF.search(" ".join(field.description.split()))
            if not match:
                continue
            named = alias(match["structure"])
            wanted = {match["field"], match["acronym"]} - {None}
            others = [
                (other, of.source)
                for of in document.structures
                if alias(of.name).endswith(named)
                for other in all_fields(of.fields)
                if other is not field and wanted & {other.name, other.acronym}
            ]
            encodings = {o.encoding for o, _ in others if o.encoding}
            orders = {o.byte_order for o, _ in others if o.byte_order}
            if not field.encoding and len(encodings) == 1:
                field.encoding = encodings.pop()
                field.encoding_from = next(s for o, s in others if o.encoding)
            if not field.byte_order and len(orders) == 1:
                field.byte_order = orders.pop()
                field.byte_order_from = next(s for o, s in others if o.byte_order)

    # A field that holds bytes of another field takes the encoding of that field.
    for structure in document.structures:
        for field in all_fields(structure.fields):
            match = REGEX_BYTES_OF.search(" ".join(field.description.split()))
            if field.encoding or not match:
                continue
            for of in document.structures:
                if (of.source.document, of.source.figure_nr) != (
                    structure.source.document,
                    int(match["figure"]),
                ):
                    continue
                other = next(
                    (o for o in all_fields(of.fields) if o.acronym == match["acronym"]),
                    None,
                )
                if other and other.encoding:
                    field.encoding, field.encoding_from = other.encoding, of.source

    # A field that holds an NQN takes the encoding of the NQN fields that state one.
    stated = [
        (field, structure.source)
        for structure in document.structures
        for field in all_fields(structure.fields)
        if is_nqn(field) and field.encoding and not field.encoding_from
    ]
    if len({f.encoding for f, _ in stated}) == 1:
        (stating, source), *_ = stated
        for structure in document.structures:
            for field in all_fields(structure.fields):
                if is_nqn(field) and not field.encoding:
                    field.encoding, field.encoding_from = stating.encoding, source

    # A field takes the byte order or the encoding of the fields of the same name,
    # acronym and width in another document that state it, where all such fields agree.
    alike: Dict[Tuple, List[Tuple[Bits, Source]]] = {}
    for structure in document.structures:
        for field in all_fields(structure.fields):
            if field.acronym and field.name and field.width:
                key = (field.name, field.acronym, field.width, field.unit)
                alike.setdefault(key, []).append((field, structure.source))
    for same in alike.values():
        for field, source in same:
            if field.unit != "bytes" or (field.width or 0) < 2:
                continue
            others = [(o, s) for o, s in same if s.document != source.document]
            orders = {
                o.byte_order
                for o, _ in others
                if o.byte_order and not o.byte_order_from
            }
            if not field.byte_order and len(orders) == 1:
                field.byte_order = orders.pop()
                field.byte_order_from = next(
                    s for o, s in others if o.byte_order and not o.byte_order_from
                )
            encodings = {
                o.encoding for o, _ in others if o.encoding and not o.encoding_from
            }
            if not field.encoding and len(encodings) == 1:
                field.encoding = encodings.pop()
                field.encoding_from = next(
                    s for o, s in others if o.encoding and not o.encoding_from
                )


REGEX_PART = re.compile(
    r"^(?P<before>.*?)\s*\b(?P<part>Lower|Low|Upper|High)\b\s*(?P<after>.*)$"
)
REGEX_BITS_PART = re.compile(r"^(?P<name>.+?)\s*\[(?P<upper>\d+):(?P<lower>\d+)\]$")


def link_parts(document: SpecDocument) -> None:
    """
    Set 'part' on the two fields of a value split over two fields, in the dwords of a
    command, a feature or an operation, or in a structure. The fields are "X Lower" and
    "X Upper", or "X Low" and "X High", for example NUMDL and NUMDU of Get Log Page. The
    fields can also be "X[63:00]" and "X[127:64]", for example the Key of KV 1.4, where
    the names give the bits of the value.
    """

    def parts(fields: List[Bits]) -> None:
        within = list(fields_within(fields))
        named = {f.name: f for f in within if f.name}
        for field in within:
            match = REGEX_PART.match(field.name or "")
            if not match or match["part"] not in ("Lower", "Low"):
                continue
            other = "Upper" if match["part"] == "Lower" else "High"
            upper = named.get(
                " ".join(p for p in (match["before"], other, match["after"]) if p)
            )
            if upper is None or not field.width:
                continue
            name = " ".join(p for p in (match["before"], match["after"]) if p)
            acronym = None
            low, high = field.acronym or "", upper.acronym or ""
            if low[:-1] and low[:-1] == high[:-1] and low[-1] == "L":
                acronym = low[:-1]
            field.part = Part(name=name, acronym=acronym, shift=0)
            upper.part = Part(name=name, acronym=acronym, shift=field.width)
        by_bits: Dict[str, List[Tuple[Bits, int]]] = {}
        for field in within:
            match = REGEX_BITS_PART.match(field.name or "")
            if match:
                by_bits.setdefault(match["name"], []).append(
                    (field, int(match["lower"]))
                )
        for name, found in by_bits.items():
            if len(found) > 1 and any(shift == 0 for _, shift in found):
                for field, shift in found:
                    field.part = Part(name=name, shift=shift)

    def of(dwords: List[Dwords]) -> List[Bits]:
        return [f for d in dwords for f in d.fields]

    for command_set in document.command_sets.values():
        for command in command_set.commands.values():
            parts(of(command.sqe))
            parts(of(command.cqe))
            for operation in command.operations:
                parts(of(operation.sqe))
                parts(of(operation.cqe))
    for feature in document.features.values():
        parts(of(feature.sqe))
        parts(of(feature.cqe))
        for operation in feature.operations:
            parts(of(operation.sqe))
            parts(of(operation.cqe))
    for structure in document.structures:
        parts(structure.fields)


def unarray_unlike(document: SpecDocument) -> None:
    """
    Clear 'array' of the entries of an array where the entries link different
    structures, or where some entries link a structure and others do not, because the
    entries of an array are alike. For example, Dword 0 to Dword 3 of the Common
    Completion Queue Entry Layout of Base 2.4 Figure 97 are not an array, because Dword
    2 and Dword 3 link Figures 98 and 99.
    """

    for _, fields in laid_out(document):
        for within in [fields] + [f.fields for f in fields_within(fields)]:
            arrays: Dict[Tuple, List[Bits]] = {}
            for field in within:
                if field.array:
                    key = (field.array.name, field.array.first, field.array.lower)
                    arrays.setdefault(key, []).append(field)
            for entries in arrays.values():
                linked = {
                    (f.structure.document, f.structure.figure_nr)
                    if f.structure
                    else None
                    for f in entries
                }
                if len(linked) > 1:
                    for field in entries:
                        field.array = None


def unlink_itself(document: SpecDocument) -> None:
    """
    Clear 'structure' of a field linked to a structure whose only field has the acronym
    and the range of the field, because that structure is the field itself. For example,
    ESUBNQN of Base 2.4 Figure 385 cites Figure 381, the data buffer of Create Exported
    NVM Subsystem, whose only field is ESUBNQN at 255:00.
    """

    alone = {
        (s.source.document, s.source.figure_nr): s.fields[0]
        for s in document.structures
        if len(s.fields) == 1
    }
    for _, fields in laid_out(document):
        for field in fields_within(fields):
            if not field.structure:
                continue
            only = alone.get((field.structure.document, field.structure.figure_nr))
            if only and (only.acronym, only.range) == (field.acronym, field.range):
                field.structure = None


def link_runs(document: SpecDocument) -> None:
    """
    Link each entry of a run to the one structure that the entries of the same width
    link. A run is fields whose names differ only by a last index, for example "SC Entry
    0" and "SC Entry 1", or "Descriptor 1", "Descriptor 2" and "Descriptor n". SC Entry
    1 of Base 2.4 Figure 361 is linked to the Secondary Controller Entry of Figure 362,
    as SC Entry 0 is, which is "defined in Figure 362". Where the entries link several
    structures, each entry is linked to the structure named as the run. Subsystem
    Namespace Descriptor n of Boot 1.4 Figure 16 cites Figure 9 for the field NUMSSNS,
    and it is linked to Subsystem Namespace (SSNS) Descriptor of Figure 17, as
    Descriptor 1 is.
    """

    def siblings(fields: List[Bits]) -> Iterator[List[Bits]]:
        yield fields
        for field in fields:
            yield from siblings(field.fields)

    def stem(field: Bits) -> Optional[str]:
        match = re.fullmatch(r"(.+?) (?:\d+|[nN]|[0-9A-F]+h)", field.name or "")
        return match[1] if match else None

    names = {
        (s.source.document, s.source.figure_nr): alias(
            re.sub(r"\s*\([^)]*\)", "", s.title)
        )
        for s in document.structures
    }
    lists = [s.fields for s in document.structures]
    lists += [d.fields for described in document.dwords.values() for d in described]
    for fields in (f for top in lists for f in siblings(top)):
        at = 0
        while at < len(fields):
            named = stem(fields[at])
            end = at + 1
            while named and end < len(fields) and stem(fields[end]) == named:
                end += 1
            run, at = fields[at:end], end
            linked = {
                (f.structure.document, f.structure.figure_nr): f.structure
                for f in run
                if f.structure
            }
            if len(run) < 2 or not linked:
                continue
            if len(linked) > 1:
                linked = {
                    k: v
                    for k, v in linked.items()
                    if names.get(k) == alias(named or "")
                }
            if len(linked) == 1:
                (structure,) = linked.values()
                widths = {f.width for f in run if f.structure == structure}
                for field in run:
                    if field.width in widths:
                        field.structure = structure


def link_extended(document: SpecDocument) -> None:
    """
    Set 'extends' on each structure that lays out bytes from other than byte 0 and that
    its text gave no 'extends'. The extended structure is the structure from byte 0 with
    the most fields of the same acronym and bytes, preferring a structure of another
    document. For example, NVM 1.3 Figure 126, with AWUN at 527:526, AWUPF and ACWU,
    extends Identify Controller of Base 2.4 Figure 338, which has these fields too.
    Where two structures have the same number of such fields, the structure extends
    neither.
    """

    whole = [s for s in document.structures if first_byte(s) == 0]
    keyed = [
        (s, {(f.acronym, f.lower, f.upper) for f in s.fields if f.acronym})
        for s in whole
    ]
    for structure in document.structures:
        if structure.extends or not first_byte(structure):
            continue
        own = {
            (f.acronym, f.lower, f.upper)
            for f in structure.fields
            if f.acronym and f.kind == "span"
        }
        scored = sorted(
            (
                (
                    len(own & fields),
                    other.source.document != structure.source.document,
                ),
                at,
            )
            for at, (other, fields) in enumerate(keyed)
            if own & fields
        )
        if not scored or len(scored) > 1 and scored[-1][0] == scored[-2][0]:
            continue
        structure.extends = keyed[scored[-1][1]][0].source


REGEX_DATA_STRUCTURE = re.compile(r"\s+Data Structure$", re.IGNORECASE)


def link_structures(document: SpecDocument) -> None:
    """
    Set 'structure' on each field that has no subfields and whose description
    refers to the figure of a structure in the same document, for example
    LBAF0 of Identify Namespace, "defined in Figure 125". Of the structures
    referred to, the field is linked to the one as wide as the field: the
    description of LBAF0 also refers to Figure 127, which is wider. An entry
    of an array that refers to no such figure is linked to the one structure,
    as wide as the entry, whose name appears in its description, for example
    "an I/O Command Set Vector". A field whose description refers to no
    figure is linked to the one structure as wide as it in a section its
    description cites, as VER of Identify Controller to VS, "defined in
    section 3.1.4.2", or else in the section of its own figure or one below
    it, whose name ends in the field's name, as CATTR of the ranges of
    Dataset Management to the "Dataset Management - Context Attributes". Of
    several in a section cited, it is the one whose fields the others
    divide further, as SGL1 to the Generic SGL Descriptor Format. A field
    named with a number, as "PRP Entry 1", is otherwise linked to the one
    structure as wide as it captioned with that name, as "PRP Entry - Page
    Base Address and Offset". A field whose description refers to a figure
    where none is as wide, as "Refer to Figure 95." of SGL1 in Connect, has
    the link of the field of the same acronym and range in that figure. An
    entry of an array of no known size, as "Power Histogram Descriptor 0" at
    "63+PHDS:64", is linked to the one figure it cites. An entry of an array
    named as a structure is captioned, apart from "Data Structure", is linked
    to that structure, as "Registrant Data Structure 0" to "Registrant".
    All entries of an array get the structure
    that any of them has. A structure that lays out the entries of an array
    becomes a data structure whatever its caption says, and uncovered() then
    checks its fields for gaps.
    """

    structures = {
        (s.source.document, s.source.figure_nr): s for s in document.structures
    }
    widths = {key: bits_wide(structure) for key, structure in structures.items()}
    referring: List[Tuple[Bits, List[Tuple[str, int]]]] = []

    def cited(field: Bits, source: Source) -> List[Tuple[str, int]]:
        # A figure given as an example, as "(e.g., the Create I/O Completion
        # Queue command (refer to Figure 571))" of PRP1, lays out one case
        described = REGEX_EXAMPLE.sub("", field.description)
        return [
            (source.document, int(number))
            for number in dict.fromkeys(REGEX_FIGURE.findall(described))
            if int(number) != source.figure_nr
        ]

    def general(keys: List[Tuple[str, int]]) -> List[Tuple[str, int]]:
        # The format the others refine: each of them divides its bytes where
        # it does, as the Generic SGL Descriptor Format of the SGL descriptors
        bounds = {
            key: {
                (f.lower or 0) * (8 if f.unit == "bytes" else 1)
                for f in structures[key].fields
            }
            for key in keys
        }
        return [k for k in keys if all(bounds[k] <= bounds[o] for o in keys if o != k)]

    def spanning(field: Bits, source: Source) -> List[Tuple[str, int]]:
        # A layout of bits at their positions in the dword, for example the Status Field
        # of Base 2.4 Figure 101 at bits 31:17, the bits of STATUS
        return [
            key
            for key, structure in structures.items()
            if key[0] == source.document
            and key[1] != source.figure_nr
            and field.unit == "bits"
            and structure.unit == "bits"
            and structure.fields
            and min(f.lower or 0 for f in structure.fields) == field.lower
            and max(f.upper or 0 for f in structure.fields) == field.upper
            and widths[key] != (field.width or 0)
        ]

    def laying_out(field: Bits, source: Source) -> Optional[Source]:
        size = field.array.stride if field.array and field.array.stride else field.width
        bits = (size or 0) * (8 if field.unit == "bytes" else 1)
        named = cited(field, source)
        found = [key for key in named if key in widths and widths[key] == bits]
        others = [
            key
            for key in structures
            if key[0] == source.document
            and key[1] != source.figure_nr
            and widths[key] == bits
        ]
        if not found and not named:
            # Of the structures of the sections cited, one whose only field is
            # the field itself, as DID of a CNS Specific Identifier, lays out
            # nothing of it
            sections = set(REGEX_SECTION.findall(field.description))
            found = [
                key
                for key in [*others, *spanning(field, source)]
                if structures[key].source.section in sections
                and [f.acronym for f in structures[key].fields] != [field.acronym]
            ]
            if len(found) > 1:
                found = general(found)
        if not found and not named and field.name and source.section:
            name = alias(field.name)
            found = [
                key
                for key in others
                if (structures[key].source.section or "").startswith(source.section)
                and (structures[key].source.section or "")[len(source.section) :][:1]
                in ("", ".")
                and alias(structures[key].title).endswith(f"_{name}")
            ]
        numbered = re.fullmatch(r"(.+?)\s+\d+", field.name or "")
        if not found and not named and numbered:
            subject = alias(numbered[1])
            found = [
                key
                for key in others
                if alias(structures[key].title.split(" - ")[0]) == subject
                and [alias(f.name or "") for f in structures[key].fields] != [subject]
            ]
        if not found and field.array:
            text = f" {alias(field.description).replace('_', ' ')} "
            found = [
                key
                for key, structure in structures.items()
                if key[0] == source.document
                and key[1] != source.figure_nr
                and widths[key] == bits
                and "_" in alias(structure.title)
                and f" {alias(structure.title).replace('_', ' ')} " in text
            ]
        if not found and field.array and not bits:
            # An entry of no known size, as "Power Histogram Descriptor 0" at
            # "63+PHDS:64", is laid out by the one figure it cites
            found = [key for key in named if key in structures]
        if not found and field.array:
            # The array is named as the structure is captioned, but for "Data
            # Structure", as "Registrant Data Structure" of Base 2.4 Figure 671
            name = alias(REGEX_DATA_STRUCTURE.sub("", field.array.name))
            found = [
                key
                for key, structure in structures.items()
                if key[0] == source.document
                and key[1] != source.figure_nr
                and (not bits or widths[key] == bits)
                and alias(REGEX_DATA_STRUCTURE.sub("", structure.name)) == name
            ]
        return structures[found[0]].source if len(found) == 1 else None

    def link(fields: List[Bits], source: Source) -> None:
        arrays: Dict[Tuple[str, Optional[int]], List[Bits]] = {}
        for field in fields:
            field.structure = None
            if field.role == "field" and not field.fields:
                field.structure = laying_out(field, source)
                if field.structure is None and cited(field, source):
                    referring.append((field, cited(field, source)))
            if field.array:
                arrays.setdefault((field.array.name, field.array.lower), []).append(
                    field
                )
            link(field.fields, source)
            for case in field.cases:
                link(case.fields, source)
        for entries in arrays.values():
            linked = [e.structure for e in entries if e.structure]
            if not linked or any(other != linked[0] for other in linked):
                continue
            for entry in entries:
                entry.structure = linked[0]
            of = structures[(linked[0].document, linked[0].figure_nr)]
            if of.kind == "other":
                of.kind = "data_structure"
                told = any(e.source == of.source for e in document.errata) or any(
                    d.code == "field-name" and d.message.startswith(cite(of.source))
                    for d in document.diagnostics
                )
                if not told:
                    document.errata += uncovered(of.fields, of.unit, of.source)

    for source, fields in laid_out(document):
        link(fields, source)
    # A field that refers to a figure for its definition, as "Refer to Figure
    # 95." of SGL1, has the link of the field at the same range there
    for field, keys in referring:
        if not field.acronym:
            continue
        there = [
            other.structure
            for key in keys
            if key in structures
            for other in structures[key].fields
            if other.structure
            and other.acronym == field.acronym
            and (other.unit, other.lower, other.upper)
            == (field.unit, field.lower, field.upper)
        ]
        if there and all(other == there[0] for other in there):
            field.structure = there[0]


def subject_of(document: str) -> str:
    """The subject of a document by its title, as "NVM Command Set" of "NVM
    Express NVM Command Set Specification, Revision 1-3" """

    title = document.split(",")[0].strip()
    title = title.removeprefix("NVM Express ").removesuffix(" Specification")
    return title.strip()


def refined_by(command: List[Dwords], dwords: Dwords) -> Optional[str]:
    """
    The acronym of the one field of 'command', the dwords of a command, whose bits hold
    all the fields of 'dwords', the dwords of an operation of the command. Returns None
    where no one field holds them all.
    """

    def bits(fields: List[Bits]) -> List[Tuple[int, int, Optional[str]]]:
        return [
            (f.lower, f.upper, f.acronym)
            for f in fields
            if f.upper is not None and f.lower is not None
        ]

    laid = bits(dwords.fields)
    if not laid:
        return None
    holding = {
        acronym
        for own in command
        if (own.lower, own.upper) == (dwords.lower, dwords.upper)
        for lower, upper, acronym in bits(own.fields)
        if acronym and all(lower <= low and high <= upper for low, high, _ in laid)
    }
    return holding.pop() if len(holding) == 1 else None


def link_refined(document: SpecDocument) -> None:
    """
    Set 'refines' of the dwords of each operation whose fields lie within the bits of
    one field of the dwords of the command
    """

    for command_set in document.command_sets.values():
        for command in command_set.commands.values():
            for operation in command.operations:
                for dwords in operation.sqe:
                    dwords.refines = refined_by(command.sqe, dwords)
                for dwords in operation.cqe:
                    dwords.refines = refined_by(command.cqe, dwords)
    for feature in document.features.values():
        for operation in feature.operations:
            for dwords in operation.sqe:
                dwords.refines = refined_by(feature.sqe, dwords)
            for dwords in operation.cqe:
                dwords.refines = refined_by(feature.cqe, dwords)


def name_by_identifiers(document: SpecDocument) -> None:
    """
    Add the command set to the name of each operation selected by a Command Set
    Identifier, where the name does not say the command set. For example, the operation
    of Identify for CNS 0Ah and CSI 01h, "I/O Command Set specific Identify Namespace
    Data Structure" in KV 1.4, is named with "(Key Value)".
    """

    sets = {
        command_set.identifier: command_set.name
        for command_set in document.command_sets.values()
        if command_set.kind == "io" and command_set.identifier is not None
    }
    for command_set in document.command_sets.values():
        for command in command_set.commands.values():
            for operation in command.operations:
                named = sets.get(operation.selectors.get("CSI", -1))
                if named and named.casefold() not in operation.name.casefold():
                    operation.name = f"{operation.name} ({named})"


def link_identifiers(document: SpecDocument) -> None:
    """
    Set 'identifier' of each I/O command set to the Command Set Identifier of the entry
    of a table of identifiers, for example Base 2.4 Figure 337, that names the document
    listing the command set. For example, 03h names the Subsystem Local Memory Command
    Set specification, whose command set is "SLM".
    """

    listed: Dict[str, List[CommandSet]] = {}
    for command_set in document.command_sets.values():
        command_set.identifier = None
        for command in command_set.commands.values():
            listed.setdefault(command.source.document, []).append(command_set)
    for values in document.values:
        if "command_set_identifier_value" not in values.columns:
            continue
        for entry in values.entries:
            match = REGEX_HEX.match(entry.value)
            if not (match and entry.document):
                continue
            for command_set in listed.get(entry.document, []):
                if command_set.kind == "io":
                    command_set.identifier = int(match["hex"], 16)


def link_selections(document: SpecDocument) -> None:
    """
    Set 'selects' on each entry of a table of CNS values, 'document' on each
    entry that names the subject of a document, 'status_values' on each
    command whose name a table of status values has, and 'status_codes' on
    each command that the "Commands Affected" of a status value names. An entry the CSI
    selects, "Y" in its CSI column, that selects nothing of its own document
    selects what the same value selects in the document of each command set
    that the entries of the Command Set Identifiers name.
    """

    documents = {
        source.document
        for source in [s.source for s in document.structures]
        + [v.source for v in document.values]
    } | set(document.documents)
    by_subject = {subject_of(d).casefold(): d for d in documents if subject_of(d)}

    for values in document.values:
        for entry in values.entries:
            entry.selects = []
            entry.document = by_subject.get((entry.name or "").strip().casefold())

    sections: Dict[Tuple[str, str], List[Source]] = {}
    for structure in document.structures:
        if structure.kind in ("command_dword", "completion_dword", "example"):
            continue
        if structure.source.section:
            key = (structure.source.document, structure.source.section)
            sections.setdefault(key, []).append(structure.source)

    tables = [v for v in document.values if v.kind == "cns_values"]
    selected: Dict[Tuple[str, str], List[Source]] = {}
    for values in tables:
        for entry in values.entries:
            reference = entry.columns.get("reference", "").strip()
            if re.fullmatch(r"\d+(?:\.\d+)+", reference):
                entry.selects = list(
                    sections.get((values.source.document, reference), [])
                )
                key = (values.source.document, entry.value)
                selected.setdefault(key, []).extend(entry.selects)
    for values in tables:
        for entry in values.entries:
            cited = by_subject.get(
                subject_of(entry.columns.get("reference", "")).casefold()
            )
            if not entry.selects and cited and cited != values.source.document:
                entry.selects = list(selected.get((cited, entry.value), []))

    command_sets = [
        entry.document
        for values in document.values
        if sum(1 for e in values.entries if e.document) > 1
        for entry in values.entries
        if entry.document
    ]
    for values in tables:
        for entry in values.entries:
            if entry.selects or not entry.columns.get("csi", "").startswith("Y"):
                continue
            entry.selects = [
                source
                for other in dict.fromkeys(command_sets)
                if other != values.source.document
                for source in selected.get((other, entry.value), [])
            ]

    commands: Dict[str, List[Command]] = {}
    for command_set in document.command_sets.values():
        for command in command_set.commands.values():
            command.status_values = []
            commands.setdefault(command.name.casefold(), []).append(command)
    for values in document.values:
        if values.kind == "status_values" and values.name:
            # A caption may give the command's acronym, as "Fabric Zoning
            # Lookup (FZL) - Command Specific Status Values"
            name = re.sub(r"\s*\([A-Z0-9]+\)$", "", values.name).casefold()
            for command in commands.get(name, []):
                command.status_values.append(values.source)

    for command_set in document.command_sets.values():
        for command in command_set.commands.values():
            command.status_codes = []
    for values in document.values:
        if values.kind != "status_values":
            continue
        for entry in values.entries:
            for named in affected(entry.columns.get("commands_affected", "")):
                found = commands.get(named.casefold(), [])
                # A command of the table's own document goes first, as Read of
                # an NVM table. Where the document has none, the one command of
                # the name in another, as Read of the ZNS 1.5 table, a command
                # of NVM 1.3; where several documents have one, none of them
                own = [c for c in found if c.source.document == values.source.document]
                for command in own or (found if len(found) == 1 else []):
                    link = ValueLink(
                        source=values.source,
                        field=values.name or "",
                        value=entry.value,
                    )
                    if link not in command.status_codes:
                        command.status_codes.append(link)


def link_selectors(document: SpecDocument) -> None:
    """
    Set 'selector_in' on each case whose controlling field is no field of
    its figure, but of the structure that a field of its figure links to, by
    the name the field's description gives it, as "CDW0.PSDT"
    """

    structures = {
        (s.source.document, s.source.figure_nr): s for s in document.structures
    }

    def named(fields: List[Bits], acronym: str) -> Optional[Bits]:
        for field in fields:
            if field.acronym == acronym:
                return field
            found = named(field.fields, acronym)
            if found:
                return found
        return None

    def link(fields: List[Bits], top: List[Bits]) -> None:
        for field in fields:
            for case in field.cases:
                case.selector_in = None
                if named(top, case.selector):
                    continue
                for holder in re.findall(
                    rf"\b(\w+)\.{re.escape(case.selector)}\b", field.description
                ):
                    linked = named(top, holder)
                    target = linked.structure if linked else None
                    other = (
                        structures.get((target.document, target.figure_nr))
                        if target
                        else None
                    )
                    if other and named(other.fields, case.selector):
                        case.selector_in = target
                        break
                link(case.fields, top)
            link(field.fields, top)

    for structure in document.structures:
        link(structure.fields, structure.fields)


def affected(text: str) -> List[str]:
    """The command names of a "Commands Affected" cell, as "Dataset
    Management, Read, Write", without the footnote marker that may end a
    name, as the 1 of "Compare1" """

    names = re.split(r",\s*|\s+and\s+|\s+or\s+", text)
    return [re.sub(r"(?<=[a-z])\d+$", "", n.strip()) for n in names if n.strip()]


def resolve(document: SpecDocument) -> SpecDocument:
    """
    Make, from what the figures of 'document' describe, the dwords and the
    operations of its commands, its features and log pages, and the dwords of
    none of them, which are a diagnostic; whatever 'document' was made of
    before is made anew
    """

    used: set = set()
    by_name: Dict[str, List[Command]] = {}
    for command_set in document.command_sets.values():
        for name, command in command_set.commands.items():
            command.sqe, command.cqe, command.operations = [], [], []
            by_name.setdefault(name, []).append(command)

    # A command of the same name in two command sets is one command, as the
    # reservation commands that the base specification describes and the NVM
    # command set lists
    # A figure in the section of a feature is the feature's, even where its
    # caption names the command, as "Set Features - Command Dword 11" of Host
    # Metadata, and goes to the feature below
    for key, described in document.dwords.items():
        cqe = key.startswith("cqe:")
        # A caption can name the command with "Command", for example "Abort Command -
        # Completion Queue Entry Dword 0" of Base 2.4 Figure 148.
        name = key.removeprefix("cqe:")
        commands = by_name.get(name) or by_name.get(name.removesuffix("_command"), [])
        # A caption can call the command a data structure, for example "Manage Exported
        # Port Data Structure - Command Dword 10" of Base 2.4 Figure 618.
        if not commands and by_name.get(name.removesuffix("_data_structure")):
            commands = by_name[name.removesuffix("_data_structure")]
            for dwords in described:
                if not any(
                    e.code == "caption" and e.source == dwords.source
                    for e in document.errata
                ):
                    document.errata.append(
                        Erratum(
                            code="caption",
                            message=f"Figure {dwords.source.figure_nr} lays out "
                            "dwords of a command and is captioned as a data "
                            "structure",
                            found=f"{commands[0].name} Data Structure",
                            source=dwords.source,
                        )
                    )
        taken = [d for d in described if not feature_identifiers(d)]
        for command in commands:
            for dwords in taken:
                add_dwords(command.cqe if cqe else command.sqe, dwords)
        if commands and len(taken) == len(described):
            used.add(key)
        elif commands:
            used.update(placed_key(key, d) for d in taken)

    document.features, document.log_pages = {}, {}
    # The operations take their dwords before the looser matching of features
    link_directives(document, used)
    link_operations(document, used)
    link_features(document, used)
    link_titled_operations(document, used)
    link_refined(document)
    link_structures(document)
    link_runs(document)
    unlink_itself(document)
    unarray_unlike(document)
    link_parts(document)
    link_extended(document)
    link_encodings(document)
    link_log_pages(document)
    link_values(document)
    link_selections(document)
    link_identifiers(document)
    name_by_identifiers(document)
    link_selectors(document)
    name_structures(document)

    # A gap where a field was left out as an erratum is that erratum again
    document.errata = [e for e in document.errata if e.code != "gap"]
    excluded = {
        (e.source.document, e.source.figure_nr)
        for e in document.errata
        if e.code.startswith("range")
    }
    for command_set in document.command_sets.values():
        for command in command_set.commands.values():
            document.errata += [
                e
                for e in gaps(command)
                if (e.source.document, e.source.figure_nr) not in excluded
            ]

    document.unassigned = unassigned_of(document.dwords, used)
    document.diagnostics = [
        d for d in document.diagnostics if d.code != "dwords-unassigned"
    ]
    for key, unassigned in document.unassigned.items():
        for d in unassigned:
            document.diagnostics.append(
                warning(
                    "dwords-unassigned",
                    f"{cite(d.source)}: {dwords_named(key, d)}, of no command, "
                    "feature or directive operation",
                )
            )
    give_roles(document)
    return document


REGEX_NAMED_CODE = re.compile(r"^(?:[0-9A-F]+h|[01]+b|\d+)$")
REGEX_SECTION_NUMBER = re.compile(r"^[A-Z]?\d*(?:\.\d+)+$")
REGEX_TITLE_CODE = re.compile(
    r"\s*\((?P<label>[A-Za-z][\w /-]*?) (?P<code>[0-9A-F]+h)(?:,[^)]*)?\)$"
)


def code_value(code: str) -> int:
    """The number a code as "1Fh", "10b" or "12" writes"""

    if code.endswith("h"):
        return int(code[:-1], 16)
    if code.endswith("b"):
        return int(code[:-1], 2)
    return int(code)


def name_lists_of_names(document: SpecDocument, after_sections: bool = False) -> None:
    """
    An entry whose description is a name of more than four words, for example "Invalid
    Number of Controller Resources" of Base 2.4 Figure 104, takes the description as its
    name where the entry is in a list of names. A list is of names where no entry has
    both a name and a description, and as many entries have a name as have none,
    counting single codes only.

    In a list where no entry has both, a description of one line and at most six words,
    without a colon or a full stop, is a name too, for example "Error status" of AET or
    "Write Locked Until Power Cycle" of BP0WPS. This does not apply to an entry that
    refers to a section, because the title of the section names the entry. With
    'after_sections', after the titles have named the entries, it applies to the entries
    that refer to a section too. A range of values is left unchanged.
    """

    lists = [values.entries for values in document.values]
    lists += [field.values for field, _ in fields_with_sources(document)]
    for entries in lists:
        codes = [e for e in entries if REGEX_NAMED_CODE.match(e.value)]
        named = [e for e in codes if e.name]
        unnamed = [e for e in codes if not e.name]
        if any(e.description for e in named):
            continue
        for entry in unnamed:
            text = normalize_text(entry.description)
            # A code that refers to a section takes the title of the cited section,
            # where that title names the code. name_by_sections() runs next.
            reference = entry.columns.get("reference", "").strip()
            short = is_short_name(entry.description) and (
                after_sections or not re.match(r"^[A-Z]?\d+(?:\.\d+)*$", reference)
            )
            if is_long_name(text) and len(named) >= len(unnamed) or short:
                entry.name, entry.description = text, ""


# The columns whose text is the name of the value of their row, for example "Delete" of
# SEL 01h of Base 2.4 Figure 397, "Idle" of SANS 0h of Figure 312, and "Configuration
# Get" of the Command Messages of MI 2.2
NAME_COLUMNS = (
    "operation",
    "management_operation",
    "command_message",
    "nvm_command_set",
    "status_code",
    "state",
    "granularity",
)
REGEX_NAME_ACRONYM = re.compile(r"^(?P<acronym>[A-Z][A-Z0-9]+): (?P<name>[A-Z].*)$")
REGEX_NAME_ASIDE = re.compile(r"\s*\((?P<aside>(?:refer to|i\.e\.,) [^()]*)\)\s*")
# The initials of the name in a parenthesis after the name, for example "Get Active
# ZoneGroup (GAZ) operation" of ORI 1 in Base 2.4 Figure 330
REGEX_NAME_INITIALS = re.compile(
    r"^(?P<name>[A-Z][\w/-]*(?: [\w/-]+)*) \((?P<acronym>[A-Z][A-Z0-9]+)\)"
    r"(?: (?P<after>operation))?$"
)
# A parenthesis at the end of a name, for example "(no shutdown has been requested)" of
# SHST 00b in Base 2.4 Figure 42. The parenthesis is prose where it has two words in
# lower case.
REGEX_NAME_PROSE = re.compile(r"^(?P<name>[^()]+?) \((?P<aside>[^()]+)\)$")
REGEX_SHORT_SENTENCE = re.compile(r"^[A-Za-z0-9][^:;.()]*\.?$")


def is_initials(acronym: str, name: str) -> bool:
    """
    Whether 'acronym' is made of initials of the words of 'name', in order, from the
    initial of the first word to the initial of the last word, for example GAZ of "Get
    Active ZoneGroup" and AAZ of "Add or Replace Active ZoneGroup"
    """

    initials = "".join(word[0].upper() for word in name.split())
    rest = iter(initials[1:-1])
    return (
        len(acronym) >= 2
        and acronym[0] == initials[0]
        and acronym[-1] == initials[-1]
        and all(letter in rest for letter in acronym[1:-1])
    )


REGEX_NAME_SENTENCE = re.compile(
    r"^(?P<name>[A-Z][\w/-]*(?: [\w/-]+){0,2})\. (?P<rest>.+)$"
)


def tidy_value_names(document: SpecDocument) -> None:
    """
    Make the name of each value a name alone. "CAP: Controller Capabilities" of Base 2.4
    Figure 33 is the name "Controller Capabilities" with the acronym "CAP". An aside in
    a name, "(refer to ...)" or "(i.e., ...)", moves to the description, for example of
    "HMAC SHA-256 (refer to RFC 6234)". Where a name has a colon, for example "Transport
    Specific" of Figure 33, the text before the colon is the name and the text after it
    moves to the description. A value without a name takes the text of a column that
    names it, for example "Delete" of SEL 01h of Figure 397. Otherwise it takes a first
    sentence of at most three words, for example "Low" of "Low. Smallest possible
    latency." of NVM 1.3 Figure 48, where no other value of the list has that name.
    """

    def described(entry: Entry, text: str) -> None:
        text = text.strip()
        if text:
            if text.startswith("refer to"):
                text = text[0].upper() + text[1:]
            entry.description = f"{entry.description} {text}".strip()

    lists = [values.entries for values in document.values]
    lists += [field.values for field, _ in fields_with_sources(document)]
    # The values of a case, for example ZRAS 0h "List all zones." of the case of ZNS 1.4
    # Figure 35 where ZRA is 00h
    lists += [
        case.values
        for field, _ in fields_with_sources(document)
        for case in field.cases
    ]
    for entries in lists:
        for entry in entries:
            if not entry.name and REGEX_NAMED_CODE.match(entry.value):
                for column in NAME_COLUMNS:
                    text = " ".join(entry.columns.get(column, "").split())
                    if text:
                        entry.name = text.split(": ")[0]
                        break
            if not entry.name or "\n" in entry.name:
                continue
            match = REGEX_NAME_ACRONYM.match(entry.name)
            if match:
                entry.acronym, entry.name = match["acronym"], match["name"]
            acronym = entry.columns.get("acronym", "").strip()
            if not entry.acronym and re.fullmatch(r"[A-Z][A-Z0-9]+", acronym):
                entry.acronym = acronym
            initials = REGEX_NAME_INITIALS.match(entry.name)
            if (
                initials
                and not entry.acronym
                and is_initials(initials["acronym"], initials["name"])
            ):
                entry.acronym = initials["acronym"]
                entry.name = " ".join(
                    part for part in (initials["name"], initials["after"]) if part
                )
            prose = REGEX_NAME_PROSE.match(entry.name)
            if prose and is_aside(prose["aside"], prose["name"]):
                entry.name = prose["name"]
                described(entry, prose["aside"])
            for aside in REGEX_NAME_ASIDE.finditer(entry.name):
                described(entry, aside["aside"])
            entry.name = REGEX_NAME_ASIDE.sub(" ", entry.name).strip()
            head, colon, rest = entry.name.partition(": ")
            if colon and len(head.split()) <= 6 and not re.search(r"\d", head):
                entry.name = head
                described(entry, rest)
        sentences = {}
        for entry in entries:
            text = " ".join(entry.description.split())
            match = REGEX_NAME_SENTENCE.match(text)
            if not entry.name and REGEX_NAMED_CODE.match(entry.value) and match:
                sentences[id(entry)] = (match["name"], match["rest"])
        taken = [e.name.casefold() for e in entries if e.name]
        taken += [name.casefold() for name, _ in sentences.values()]
        for entry in entries:
            if id(entry) in sentences:
                name, rest = sentences[id(entry)]
                if taken.count(name.casefold()) == 1:
                    entry.name, entry.description = name, rest
        # Where another value or a range of reserved values has a name, a definition of
        # one short sentence is a name. Examples are "No action" of MO 00h beside
        # "Reclaim Unit Handle Status" in Base 2.4 Figure 651, and "4 bytes" of PRS 000b
        # beside the reserved range "010b to 111b". A name followed by its initials is a
        # name too, for example "Add or Replace Active ZoneGroup (AAZ) operation" of ORI
        # 2.
        if not any(e.name for e in entries):
            continue
        for entry in entries:
            text = " ".join(entry.description.split())
            if entry.name or not REGEX_NAMED_CODE.match(entry.value):
                continue
            initials = REGEX_NAME_INITIALS.match(text)
            if initials and is_initials(initials["acronym"], initials["name"]):
                entry.acronym, entry.description = initials["acronym"], ""
                entry.name = " ".join(
                    part for part in (initials["name"], initials["after"]) if part
                )
            elif (
                REGEX_SHORT_SENTENCE.match(text)
                and len(text.split()) <= 6
                and not value_names(entry)
            ):
                entry.name, entry.description = text.removesuffix("."), ""


def is_short_name(description: str) -> bool:
    """
    Whether 'description' is a name in a list of names: one line of at most six words
    that begins with a capital and has no colon or full stop, for example "Error status"
    or "No notification and no effect"
    """

    text = description.strip()
    return (
        bool(text)
        and "\n" not in text
        and text[0].isupper()
        and len(text.split()) <= 6
        and not re.search(r"[:.;]", text)
    )


def label_of(values: Values, sections: Dict[str, str]) -> Optional[str]:
    """The label that the titles of the sections cited by the references of
    'values' name their codes by most often, as "CNS" of "(CNS 01h)" for the
    CNS values of Identify; None where no title names a code"""

    labels: Dict[str, int] = {}
    for entry in values.entries:
        number = entry.columns.get("reference", "").strip()
        if REGEX_SECTION_NUMBER.match(number) and number in sections:
            match = REGEX_TITLE_CODE.search(sections[number])
            if match:
                labels[match["label"]] = labels.get(match["label"], 0) + 1
    return max(labels, key=lambda k: labels[k]) if labels else None


def name_by_sections(document: SpecDocument, sections: Dict[str, str]) -> None:
    """
    A code that its row names in no column, as CNS 01h of Identify, takes the
    title of the section its reference column cites, "Identify Controller Data
    Structure" of 5.2.14.2.1. A title ending in a label and a code, as "(CNS
    01h)", names the code it describes; the parenthesis is left out of the
    name.

    A reference to a section whose title names another code is a candidate
    erratum, as CNS 14h citing the section of CNS 21h. A code whose reference
    fails so, or is no section, takes the section whose title names it with
    the label the table's references name, as "(CNS 02h)" for 02h, whose
    reference reads "0". A code with no reference, or reserved, is left
    unnamed. A reference to a number that the document gives two sections,
    as the Base 2.4 PDF gives 5.2.14.3.1 to those of CNS 14h and CNS 21h,
    cites the one whose title names the code.
    """

    for values in document.values:
        cited: Dict[int, Tuple[str, str]] = {}
        for i, entry in enumerate(values.entries):
            number = entry.columns.get("reference", "").strip()
            if REGEX_SECTION_NUMBER.match(number) and number in sections:
                cited[i] = (number, sections[number])
        label = label_of(values, sections)
        for i, (number, _) in list(cited.items()):
            if not REGEX_NAMED_CODE.match(values.entries[i].value):
                continue
            # Of the sections a document numbers alike, as "5.2.14.3.1" and
            # "5.2.14.3.1 (2)", the one whose title names the code
            for key, other in sections.items():
                match = REGEX_TITLE_CODE.search(other)
                if (
                    key.startswith(f"{number} (")
                    and match
                    and match["label"] == label
                    and code_value(match["code"]) == code_value(values.entries[i].value)
                ):
                    cited[i] = (number, other)
        # A code that titles of the label name more than once, as CNS 06h of
        # each command set, names no section of its own
        titled: Dict[int, List[str]] = {}
        for heading in sections.values():
            match = REGEX_TITLE_CODE.search(heading)
            if match and match["label"] == label:
                titled.setdefault(int(match["code"][:-1], 16), []).append(heading)
        by_code = {code: found[0] for code, found in titled.items() if len(found) == 1}
        for i, entry in enumerate(values.entries):
            reference = entry.columns.get("reference", "").strip()
            if (
                entry.name
                or not reference
                or not REGEX_NAMED_CODE.match(entry.value)
                or "Reserved" in entry.columns.values()
            ):
                continue
            title: Optional[str] = None
            if i in cited:
                number, title = cited[i]
                match = REGEX_TITLE_CODE.search(title)
                if (
                    match
                    and match["label"] == label
                    and int(match["code"][:-1], 16) != code_value(entry.value)
                ):
                    document.errata.append(
                        Erratum(
                            code="reference",
                            message=(
                                f"{entry.value}: the reference {number} is the "
                                f"section of {match['label']} {match['code']}, "
                                f"'{title}'"
                            ),
                            found=number,
                            source=values.source,
                        )
                    )
                    title = None
            title = title or by_code.get(code_value(entry.value))
            if title and not named_already(
                values, REGEX_TITLE_CODE.sub("", title), entry.value
            ):
                entry.name = REGEX_TITLE_CODE.sub("", title)


def name_by_documents(document: SpecDocument) -> None:
    """
    A code without a name whose reference names another document of the merged
    'document' takes the title of the one section of that document whose title names the
    code with the label of the table. For example, CNS 00h of Identify in Base 2.4 names
    "NVM Express NVM Command Set Specification", and takes "NVM Command Set Identify
    Namespace Data Structure (CNS 00h)". A reference can leave out "NVM Express", as ZNS
    1.5 does.

    A reference to "I/O Command Set Specification", for example of CNS 0Ah, names every
    document of a command set. The code takes the title that more than half of the
    documents with a section titled for the code give, ignoring letter case. A code is
    left without a name where no such title names it, where one document has several
    such titles, or where another code of the table has the title.
    """

    def titled(name: str) -> str:
        """'name' up to its first comma, as the title of a document, without
        "NVM Express", which a reference may leave out"""

        title = name.split(",")[0].strip()
        return title.removeprefix("NVM Express ")

    sections = document.sections
    for values in document.values:
        own = values.source.document
        label = label_of(values, sections.get(own, {}))
        if label is None:
            continue
        for entry in values.entries:
            reference = entry.columns.get("reference", "").strip()
            if (
                entry.name
                or not reference
                or REGEX_SECTION_NUMBER.match(reference)
                or not REGEX_NAMED_CODE.match(entry.value)
                or "Reserved" in entry.columns.values()
            ):
                continue
            if titled(reference) == "I/O Command Set Specification":
                named = [
                    stem
                    for stem in sections
                    if stem != own
                    and titled(stem).endswith(" Command Set Specification")
                ]
            else:
                named = [
                    stem
                    for stem in sections
                    if stem != own and titled(stem) == titled(reference)
                ]
            names: List[str] = []
            for stem in named:
                titles = []
                for title in sections[stem].values():
                    match = REGEX_TITLE_CODE.search(title)
                    if (
                        match
                        and match["label"] == label
                        and code_value(match["code"]) == code_value(entry.value)
                    ):
                        titles.append(REGEX_TITLE_CODE.sub("", title))
                if len(titles) == 1:
                    names.append(titles[0])
            for name in names:
                same = [n for n in names if n.casefold() == name.casefold()]
                if len(same) * 2 <= len(names):
                    continue
                chosen: Optional[str] = name
                if named_already(values, name, entry.value):
                    chosen = qualified_by_definition(values, entry, name)
                if chosen:
                    entry.name = chosen
                    break


REGEX_SPECIFIED = re.compile(
    r"\bfor the specified (?P<term>[A-Z][\w]*(?: [A-Z][\w]*)*)"
)


def qualified_by_definition(values: Values, entry: Entry, name: str) -> Optional[str]:
    """
    'name', which another code of 'values' has, qualified by what the definition of
    'entry' is for, where the definition of no other code of that name says so. For
    example, CNS 09h of Base 2.4 Figure 336, "Identify Namespace data structure for the
    specified Format Index", is "NVM Command Set Identify Namespace Data Structure for
    the specified Format Index", because NVM 1.3 gives the sections of CNS 00h and 09h
    the same title. Returns None where nothing qualifies the name.
    """

    match = REGEX_SPECIFIED.search(" ".join(entry.description.split()))
    if not match:
        return None
    others = [
        e
        for e in values.entries
        if e is not entry and (e.name or "").casefold() == name.casefold()
    ]
    if any(match["term"] in e.description for e in others):
        return None
    return f"{name} for the specified {match['term']}"


def named_already(values: Values, name: str, code: str) -> bool:
    """
    Whether a code of 'values' other than 'code' has 'name'. Where two sections have the
    same title, for example "NVM Command Set Identify Namespace Data Structure" of CNS
    00h and of CNS 09h in NVM 1.3, the title names only the first code.
    """

    return any(
        (e.name or "").casefold() == name.casefold()
        and REGEX_NAMED_CODE.match(e.value)
        and code_value(e.value) != code_value(code)
        for e in values.entries
    )


# A value of another field named in a description by its acronym and its
# name, as "ZSE:Empty" and "ZSIO:Implicitly Opened" in "List the zones in the
# ZSIO:Implicitly Opened state."
REGEX_NAMED_VALUE = re.compile(
    r"\b(?P<acronym>[A-Z][A-Z0-9]+):(?P<name>[A-Z][A-Za-z]*(?: [A-Z][A-Za-z]*)*)"
)


# The words by which a caption names a kind of structure, which distinguish two figures
# of one name
STRUCTURE_WORDS = {
    "data_structure": "Data Structure",
    "data_buffer": "Data Buffer",
}

REGEX_OFFSET_TITLE = re.compile(r"^Offset (?P<offset>.+?):\s+(?P<rest>.+)$")
REGEX_CAPABILITY_OFFSET = re.compile(
    r"^(?P<base>[A-Z][A-Z0-9]*)(?:\s*\+\s*(?P<offset>[0-9A-Fa-f]+)h?)?$"
)
# An acronym in parentheses, as "CH", "ICReq" or 'NSCQED0'
REGEX_TITLE_ACRONYM = re.compile(r"^(?=(?:[^A-Z]*[A-Z]){2})[A-Z0-9][A-Za-z0-9]*$")
# What a title gives before " - " where that is an acronym, as "CC", "SQyTDBL" or
# "MLBAR (BAR0)"
REGEX_LEFT_ACRONYM = re.compile(
    r"^(?P<acronym>(?=(?:[^A-Z]*[A-Z]){2})[A-Z][A-Za-z0-9]*)(?: \([A-Z][A-Z0-9]*\))?$"
)
REGEX_TRAILING = re.compile(r"^(?P<head>.+?)\s*\((?P<inner>[^()]+)\)$")
# Words of a name that the document and the context give
REGEX_CONTEXT_WORDS = re.compile(
    r"\b(?:I/O )?Command Set (?:Specific|Independent|Dependent)\b(?: -)?\s*",
    re.IGNORECASE,
)


def name_parts(structure: Structure) -> None:
    """
    Set the name, owner, acronym, optional, qualifier and offset of 'structure' from
    its title, as "Controller Configuration" and the acronym "CC" of "CC - Controller
    Configuration"; a title giving an offset makes the structure a register
    """

    text = structure.title.strip()
    if match := REGEX_OFFSET_TITLE.match(text):
        text = match["rest"]
        where = match["offset"].strip()
        if hexadecimal := REGEX_HEX.match(where):
            structure.offset = int(hexadecimal["hex"], 16)
        elif capability := REGEX_CAPABILITY_OFFSET.match(where):
            structure.offset_base = capability["base"]
            structure.offset = int(capability["offset"] or "0", 16)
        else:
            structure.offset_formula = where
        if structure.unit == "bits":
            structure.kind = "register"
    acronym = owner = None
    while match := REGEX_TRAILING.match(text):
        inner = match["inner"].strip()
        if inner.lower() == "optional":
            structure.optional = True
        elif acronym is None and REGEX_TITLE_ACRONYM.match(inner):
            acronym = inner
        elif structure.qualifier in (None, inner):
            structure.qualifier = inner
        else:
            break
        text = match["head"].strip()
    left, dash, right = text.partition(" - ")
    if dash and right:
        if left_acronym := REGEX_LEFT_ACRONYM.match(left):
            acronym = acronym or left_acronym["acronym"]
        else:
            owner = left
        text = right
    structure.name, structure.owner, structure.acronym = text, owner, acronym


def key_candidates(structure: Structure, document_title: Optional[str]) -> List[str]:
    """
    The keys that 'structure' can have, by how much they say: the key of its name
    without the name of the document's command set, "Data Structure" and words such as
    "I/O Command Set Specific"; with those words; then with its owner, its qualifier,
    its kind and its figure number. A key that a level adds nothing to is the key of
    the level before.
    """

    name = structure.name
    if document_title and name.startswith(f"{document_title} "):
        name = name[len(document_title) + 1 :]
    name = re.sub(r"\s+(?:Data )?Structure$", "", name).strip() or structure.name
    short = REGEX_CONTEXT_WORDS.sub("", name).strip() or name
    keys = [alias(short), alias(name)]
    owner = structure.owner
    owned = owner and not alias(name).startswith(alias(owner))
    keys.append(alias(f"{owner} {name}") if owned else keys[-1])
    qualifier = structure.qualifier
    keys.append(f"{keys[-1]}_{alias(qualifier)}" if qualifier else keys[-1])
    word = STRUCTURE_WORDS.get(structure.kind)
    keys.append(f"{keys[-1]}_{alias(word)}" if word else keys[-1])
    keys.append(f"{keys[-1]}_figure_{structure.source.figure_nr}")
    return keys


def renamed_by_linking_field(document: SpecDocument) -> None:
    """
    Of two structures of a document with one title, one kind and no qualifier, name the
    later figure by the one field that links it, where that field names it
    differently. For example, NVM 1.3 Figure 190 has the caption of Figure 189,
    "Reference Exported Controller Configuration State", and is the layout of RENSCS,
    Reference Exported Namespace Configuration State. The caption is a candidate
    erratum.
    """

    groups: Dict[Tuple[str, str], List[Structure]] = {}
    for structure in document.structures:
        groups.setdefault((structure.source.document, structure.title), []).append(
            structure
        )
    linking: Dict[Tuple[str, Optional[int]], set] = {}
    for field, _ in fields_with_sources(document):
        if field.structure is not None and field.name:
            at = (field.structure.document, field.structure.figure_nr)
            linking.setdefault(at, set()).add(field.name)
    for (_, title), same in groups.items():
        if len(same) < 2 or len({s.kind for s in same}) > 1:
            continue
        if any(s.qualifier for s in same):
            continue
        for structure in same[1:]:
            source = structure.source
            names = linking.get((source.document, source.figure_nr), set())
            other = next(iter(names)) if len(names) == 1 else structure.name
            if other == structure.name:
                continue
            found = Erratum(
                code="caption",
                message=f"Figure {source.figure_nr} has the caption of "
                f"Figure {same[0].source.figure_nr}, '{title}', and is "
                f"the layout of the field {other}",
                found=title,
                source=source,
            )
            if found not in document.errata:
                document.errata.append(found)
            structure.name = other


def name_structures(document: SpecDocument) -> None:
    """
    Give every structure of 'document' the parts of its name, by name_parts(), and a key
    unique among the structures of its document, the first of key_candidates() that
    tells it apart from the others; and give the operations the keys of the structures
    they transfer
    """

    for structure in document.structures:
        name_parts(structure)
    renamed_by_linking_field(document)
    for structure in document.structures:
        structure.size = size_of(structure)
    by_document: Dict[str, List[Structure]] = {}
    for structure in document.structures:
        by_document.setdefault(structure.source.document, []).append(structure)
    for stem, structures in by_document.items():
        parts = document_parts(stem)
        title = parts[0] if parts else None
        candidates = [key_candidates(s, title) for s in structures]
        at = [0] * len(structures)
        while True:
            keys: Dict[str, List[int]] = {}
            for index in range(len(structures)):
                keys.setdefault(candidates[index][at[index]], []).append(index)
            colliding = [indices for indices in keys.values() if len(indices) > 1]
            if not colliding:
                break
            moved = False
            for indices in colliding:
                # Of a log page and other structures, the log page keeps the key
                pages = [i for i in indices if structures[i].kind == "log_page"]
                for index in indices:
                    if len(pages) == 1 and index in pages:
                        continue
                    if at[index] + 1 < len(candidates[index]):
                        at[index] += 1
                        moved = True
            if not moved:
                # Structures of one figure, as the layout of a figure read twice, are
                # told apart by their order
                for indices in colliding:
                    for n, index in enumerate(indices[1:], start=2):
                        candidates[index][at[index]] += f"_{n}"
                break
        for index, structure in enumerate(structures):
            structure.key = candidates[index][at[index]]
    keys_by_title = {
        (s.source.document, s.title): s.key for s in document.structures
    }
    for operation in operations_of(document):
        operation.structures = [
            keys_by_title.get((operation.source.document, title), title)
            for title in operation.structures
        ]


def size_of(structure: Structure) -> Optional[int]:
    """
    The size of 'structure' in bytes by the highest bound of its fields, or None where
    a range of a field is a formula or open
    """

    if not structure.fields or any(f.kind != "span" for f in structure.fields):
        return None
    upper = max(f.upper for f in structure.fields if f.upper is not None)
    return upper + 1 if structure.unit == "bytes" else upper // 8 + 1


def operations_of(document: SpecDocument) -> Iterator[Operation]:
    """Every operation of the commands and the features of 'document'"""

    for command_set in document.command_sets.values():
        for command in command_set.commands.values():
            yield from command.operations
    for feature in document.features.values():
        yield from feature.operations


def fields_with_sources(
    document: SpecDocument,
) -> Iterator[Tuple[Bits, Source]]:
    """Every field of the structures and dwords of 'document', nested ones and
    those of cases too, with the figure it is of"""

    def nested(fields: List[Bits]) -> Iterator[Bits]:
        for field in fields:
            yield field
            yield from nested(field.fields)
            for case in field.cases:
                yield from nested(case.fields)

    for structure in document.structures:
        for field in nested(structure.fields):
            yield field, structure.source
    for described in document.dwords.values():
        for dwords in described:
            for field in nested(dwords.fields):
                yield field, dwords.source
    for command_set in document.command_sets.values():
        for command in command_set.commands.values():
            for dwords in [*command.sqe, *command.cqe]:
                for field in nested(dwords.fields):
                    yield field, dwords.source


def link_named_values(document: SpecDocument) -> None:
    """
    Link each entry without a name whose description names a value of another
    field, as "ZSE:Empty", to that value. The field is the one field of the
    document whose values have the name of every value the entries beside it
    name, so that a name as common as "Empty" is not taken from another
    table; where no field or more than one has them, nothing is linked.
    """

    fields = list(fields_with_sources(document))
    lists: List[List[Entry]] = [values.entries for values in document.values]
    for field, _ in fields:
        lists.append(field.values)
        lists += [case.values for case in field.cases]
    for entries in lists:
        named = {}
        for entry in entries:
            match = REGEX_NAMED_VALUE.search(entry.description)
            if entry.name is None and match:
                named[id(entry)] = (entry, match)
        if not named:
            continue
        wanted = {match["name"] for _, match in named.values()}
        found = {}
        for field, source in fields:
            have = {v.name: v for v in field.values if v.name}
            if field.values is not entries and wanted <= set(have):
                key = (source.document, source.figure_nr, field.acronym or field.name)
                found[key] = (field, source, have)
        if len(found) != 1:
            continue
        ((field, source, have),) = found.values()
        for entry, match in named.values():
            entry.refers_to = ValueLink(
                source=source,
                field=field.acronym or field.name or "",
                value=have[match["name"]].value,
                acronym=match["acronym"],
            )


class FromNormalizedDocument(Converter):
    @staticmethod
    def is_applicable(path: Path) -> bool:
        return "".join(path.suffixes).lower() == NormalizedFigureDocument.SUFFIX_JSON

    @staticmethod
    def convert(path: Path, args: Namespace) -> Tuple[Document, List[Error]]:
        normalized = NormalizedFigureDocument.model_validate_json(
            path.read_text(encoding="utf-8")
        )
        document = SpecDocument()
        document.meta.stem = strip_all_suffixes(path.stem)
        document.meta.file = normalized.meta.file
        document.meta.sha256 = normalized.meta.sha256
        document.meta.key = document_key(document.meta.stem)
        parts = document_parts(document.meta.stem)
        document.meta.name, document.meta.revision = parts or (None, None)
        document.documents[document.meta.stem] = document.meta.model_copy()
        for figure in normalized.figures:
            add_figure(document, figure, document.meta.stem)
        document.sections[document.meta.stem] = dict(normalized.sections)
        name_lists_of_names(document)
        name_by_sections(document, normalized.sections)
        name_lists_of_names(document, after_sections=True)
        tidy_value_names(document)
        document.errata += noted_errata(normalized, document.meta.stem)
        document = resolve(document)
        link_named_values(document)
        give_roles(document)
        return document, []


def merge(documents: List[SpecDocument]) -> SpecDocument:
    """
    One document of what 'documents' describe, resolved as one: a command set
    listed by more than one is one command set, and a command gets the dwords
    any of them describes; 'documents' are left as they are
    """

    merged = SpecDocument()
    merged.meta.stem = "merged"
    for document in (d.model_copy(deep=True) for d in documents):
        merged.documents.update(document.documents)
        merged.sections.update(document.sections)
        for key, command_set in document.command_sets.items():
            into = merged.command_sets.setdefault(
                key, command_set.model_copy(update={"commands": {}})
            )
            for name, command in command_set.commands.items():
                into.commands.setdefault(name, command)
        for key, described in document.dwords.items():
            merged.dwords.setdefault(key, []).extend(described)
        merged.structures += document.structures
        merged.values += document.values
        merged.errata += document.errata
        merged.diagnostics += [
            d for d in document.diagnostics if d.code != "dwords-unassigned"
        ]
    name_by_documents(merged)
    merged = resolve(merged)
    hashes = [meta.sha256 for meta in merged.documents.values()]
    if hashes and all(hashes):
        merged.meta.input_sha256 = senfd.identity.input_sha256(h for h in hashes if h)
        merged.meta.combined_sha256 = senfd.identity.combined_sha256(
            merged.meta.input_sha256, merged.meta.senfd_sha256
        )
    return merged
