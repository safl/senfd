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
from typing import ClassVar, Dict, Iterator, List, Literal, Optional, Tuple

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
from senfd.normalize import CaptionKind, Diagnostic, note, warning
from senfd.ranges import RangeKind, Unit
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
    """The order of the field's bytes where the figure marks the byte of its
    most significant bit (MSB) and that of its least (LSB), as the
    protection information formats of the NVM Command Set do: "big-endian"
    where the MSB is in the lowest byte. None where the figure does not mark
    them, or the field is one byte"""
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
    """The index of this entry, for example 63 for LBAF63; None for a last
    entry whose range the figure gives as a formula"""
    first: int
    """The index of the first entry, 0 or 1 depending on the figure"""
    count: Optional[int] = None
    """The number of entries, for example 64; None where the figure gives the
    range of the last entry as a formula, because the number is then a value
    in the data"""
    stride: int
    """The size of one entry, in the unit of the field"""
    lower: int
    """The offset of the first entry, which is where the array starts"""


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


class Dwords(Model):
    """The dwords 'lower' to 'upper' of a command, and their fields"""

    lower: int
    """The first dword, as 10 of CDW10"""
    upper: int
    """The last dword, the same as 'lower' for one dword"""
    condition: Optional[str] = None
    """Where the figure lays the dwords out only under a condition, the
    condition, as 'CETYPE is cleared to 0h'"""
    qualifier: Optional[str] = None
    """What the caption says the dwords are of, as 'NVM Command Set Specific
    Fields'"""
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
    """The names of the structures the operation transfers"""
    source: Source
    """The figure listing the operation"""


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
    columns: Dict[str, str] = Field(default_factory=dict)
    """The opcode table's other columns of the command, by their keys"""
    source: Source
    """The opcode table listing the command"""


class CommandSet(Model):
    """The commands of an opcode table, as Admin or NVM"""

    name: str
    """The name of the command set"""
    commands: Dict[str, Command] = Field(default_factory=dict)
    """Its commands, by their names as keys, as 'zone_append'"""


class Structure(Model):
    """
    A layout of fields that is no command's dwords: a data structure, a log
    page, a register or anything else a figure lays out
    """

    name: str
    """The name its caption gives, as 'CC - Controller Configuration'"""
    kind: CaptionKind
    """What its caption says it is, as "data_structure", "log_page" or
    "register", or 'other'"""
    unit: Unit
    """What its fields' ranges count: "bits" or 'bytes'"""
    qualifier: Optional[str] = None
    """What the caption says it is of, as 'Log Specific Field'"""
    offset: Optional[str] = None
    """Of a register, its offset, as '14h'"""
    fields: List[Bits] = Field(default_factory=list)
    """Its fields"""
    notes: List[str] = Field(default_factory=list)
    """The notes of the figure"""
    source: Source
    """The figure laying it out"""


TypedKind = Literal[
    "level",
    "flag",
    "identifier",
    "number",
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
            (["note"], "note", "integer"),
            (["reference"], "reference", "string"),
        )
    ]
}


class Typed(Model):
    """
    A value of a table as what it is: a requirement "level" (M, O, P, NR, R),
    a yes or no "flag", an "identifier" or a range of them, a "note" it is
    given by, a "reference" to another specification, or "reserved",
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
    """Of a range of identifiers, the last"""
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
    description: str = ""
    """The text of the row's description"""
    columns: Dict[str, str] = Field(default_factory=dict)
    """The row's other columns, by their keys"""
    typed: Dict[str, Typed] = Field(default_factory=dict)
    """The values of the row's columns of a known kind, by their keys"""


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
    sqe: List[Dwords] = Field(default_factory=list)
    """The submission queue entry dwords described for it"""
    cqe: List[Dwords] = Field(default_factory=list)
    """The completion queue entry dwords described for it"""
    source: Source
    """The feature identifier table listing it"""


class LogPage(Model):
    """A log page, by its identifier, and the structure laying it out"""

    identifier: int
    """The log page identifier, as 2 of 02h"""
    name: str
    """The name of the log page, as 'SMART / Health Information'"""
    columns: Dict[str, str] = Field(default_factory=dict)
    """The log page identifier table's other columns of it, by their keys"""
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
]


class Erratum(Model):
    """
    Something of a figure that is not what its kind of value must be, as a
    range beyond the dword it is of, left out of the model; or fields that do
    not fit together, as two of the same bits, which the model keeps. Each is
    a candidate erratum of the specification, saying where it is.
    """

    code: ErratumCode
    """What kind it is: "value", "acronym", "range" (text that is no range),
    "range-outside", "range-reversed", "opcode", "gap" (of a command's
    dwords), 'layout-gap' (of a structure) or "reference" (to the section of
    another value)"""
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
    documents: Dict[str, DocumentMeta] = Field(default_factory=dict)
    """The documents the data model is of, by name, each with the file it
    was made from and the file's SHA-256, by which a published one is known"""


def document_name(document: str) -> str:
    """A document by a short name, as "Base 2.2" """

    match = re.match(
        r"NVM Express (?P<name>.+?) Specification,? Revision (?P<revision>[\d\-.]+)",
        document,
    )
    if not match:
        return document
    name = re.sub(r" Command Set$", "", match["name"])
    return f"{name} {match['revision'].replace('-', '.')}"


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
    name = key.removeprefix("cqe:").replace("_", " ")
    name = re.sub(r" command$", "", name)
    of = f"the completion of {name}" if completion else name
    return f"dwords {dwords.lower}:{dwords.upper} of {of}"


def without_footnote(name: str) -> str:
    """'name' without a footnote marker, as "Flush4" or "Cancel 4" is "Flush" and
    "Cancel" """

    return re.sub(r"(?<=[A-Za-z)])\s*\d+(?:,\s*\d+)*$", "", name.strip())


def command_set_name(name: str) -> str:
    """The name of a command set, as its opcode table's caption gives it, without
    "Command Set" and "I/O" after it: "NVM Command Set" is "NVM" """

    stripped = re.sub(r"(?:\s+Command Set)?(?:\s+I/O)?$", "", name.strip())
    return stripped or name.strip()


def alias(name: str) -> str:
    """The key of a name: lower case, words joined by underscores"""

    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


REGEX_HEX = re.compile(r"^(?P<hex>[0-9A-Fa-f]+)h$")


def byte_order_of(
    columns: Dict[str, str],
) -> Optional[Literal["big-endian", "little-endian"]]:
    """The byte order the columns "msb_byte" and "lsb_byte" of a byte diagram
    give a field, or None where they are not both numbers or are the same"""

    msb, lsb = columns.get("msb_byte", ""), columns.get("lsb_byte", "")
    if not (msb.isdigit() and lsb.isdigit()) or int(msb) == int(lsb):
        return None
    return "big-endian" if int(msb) < int(lsb) else "little-endian"


def bits_of(field: LayoutField, unit: Unit) -> ReadBits:
    return ReadBits(
        name=field.name,
        acronym=field.acronym,
        unit=unit,
        upper=field.range.upper,
        lower=field.range.lower,
        range=field.range.text,
        description=field.description,
        section=field.section,
        elided=field.elided,
        columns=field.columns,
        byte_order=byte_order_of(field.columns),
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
            rng = senfd.ranges.parse(field.unit, field.range, width)
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
                values=field.values,
                cases=cases,
            )
        )

    for field_made in kept:
        for case_made in field_made.cases:
            decide(case_made, kept)
    arrays_of(kept)
    return kept, errata, unnamed


def decide(case: Case, fields: List[Bits]) -> None:
    """Set the selector of 'case' to the acronym of the controlling field,
    found among 'fields', and set the number of each value in 'case.when'.
    The number comes from the controlling field's value of that name, or from
    the code that the case writes in place of a name."""

    names = (alias(case.selector),)
    by = next(
        (
            f
            for f in fields
            if alias(f.name) in names or alias(f.acronym or "") in names
        ),
        None,
    )
    if by is None:
        return
    case.selector = by.acronym or by.name
    numbers: Dict[str, int] = {}
    for value in by.values:
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
    return [
        (name[: match.start()], int(match[0]), name[match.end() :])
        for match in re.finditer(r"\d+", name)
    ]


def arrays_of(fields: List[Bits]) -> None:
    """
    Set 'array' on each of 'fields' that is an entry of an array. The entries
    are adjacent fields whose acronyms, or names where they have no acronym,
    differ only by a number, with rows left out between two of them. Each
    entry must have the same width and lie at the offset that its index
    gives. The last entry may be given by a formula, for example "Entry
    NUMENT-1"; the array then has no count.
    """

    def entry(field: Bits, of: str, before: str, after: str) -> Optional[int]:
        """The index of 'field' where its name is 'before', a number and
        'after', and otherwise None"""

        for prefix, number, suffix in numbered(getattr(field, of)):
            if (prefix, suffix) == (before, after) and field.kind == "span":
                return number
        return None

    for at, last in enumerate(fields):
        if not last.elided or at == 0 or last.array or fields[at - 1].array:
            continue
        above = fields[at - 1]
        if above.kind != "span":
            continue
        of = "acronym" if above.acronym else "name"
        text = getattr(last, of) or ""
        for before, _, after in numbered(getattr(above, of)):
            closes = last.kind == "formula" and text.startswith(before)
            if entry(last, of, before, after) is not None or (
                closes and text.endswith(after) and len(text) > len(before + after)
            ):
                break
        else:
            continue

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
        if not stride or any(
            f.width != stride or f.lower != (lowest.lower or 0) + (i - first) * stride
            for i, f in spans
        ):
            continue
        whole = len(spans) == len(run)
        name = next(
            (b + a for b, n, a in numbered(lowest.name) if n == first), lowest.name
        )
        for index, field in zip(indexes, run):
            field.array = Array(
                name=" ".join(name.split()),
                acronym=before + after if of == "acronym" else None,
                index=index,
                first=first,
                count=max(i for i, _ in spans) - first + 1 if whole else None,
                stride=stride,
                lower=lowest.lower or 0,
            )


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
            alias(set_name), CommandSet(name=set_name)
        )
        for entry in figure.entries:
            match = REGEX_HEX.match(entry.get("opcode", ""))
            name = without_footnote(entry.get("command", ""))
            if not name:
                continue
            if not match:
                # Reserved and vendor specific opcodes are given as ranges
                if entry.get("opcode") and " to " not in entry["opcode"]:
                    document.errata.append(
                        Erratum(
                            code="opcode",
                            message=f"Command {name}: opcode is not a value",
                            found=entry.get("opcode", ""),
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
                    k: v for k, v in entry.items() if k not in ("opcode", "command")
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

    if dwords and subject.name:
        # A caption can give the acronym of the command after its name
        name = re.sub(r"\s*\([A-Z0-9]+\)$", "", subject.name)
        key = ("cqe:" if subject.kind == "completion_dword" else "") + alias(name)
        fields, errata, unnamed = checked(
            fields_of(figure.layout), 32 * (dwords[1] - dwords[0] + 1), source
        )
        took(document, errata, unnamed, source)
        document.dwords.setdefault(key, []).append(
            Dwords(
                lower=dwords[0],
                upper=dwords[1],
                condition=subject.condition,
                qualifier=subject.qualifier,
                fields=fields,
                source=source,
            )
        )
        return

    fields, errata, unnamed = checked(fields_of(figure.layout), None, source)
    if subject.kind in WHOLE and not (errata or unnamed):
        errata = uncovered(fields, figure.layout.unit, source)
    took(document, errata, unnamed, source)
    document.structures.append(
        Structure(
            name=subject.name or figure.caption,
            kind=subject.kind,
            unit=figure.layout.unit,
            qualifier=subject.qualifier,
            offset=subject.offset,
            fields=fields,
            notes=figure.layout.notes,
            source=source,
        )
    )


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
    ("number", re.compile(r"^(?P<decimal>\d+)$")),
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

    for kind, regex in TYPED_FORMS:
        match = regex.match(text.strip())
        if not match:
            continue
        groups = match.groupdict()
        footnotes = [int(n) for n in re.findall(r"\d+", groups.get("footnotes") or "")]
        typed = Typed(kind=kind, footnotes=footnotes)
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
                typed.lower = typed.upper = int(groups["decimal"])
        elif kind == "note":
            typed.note = int(groups["note"])
        elif kind == "reference":
            typed.reference = groups["reference"]
        return typed
    return None


def kinds_of(column: str, values: "Values") -> Optional[set]:
    """The kinds of value a column holds, by its name and the table it is of,
    or None for a column of text"""

    if column in ("om", "i_o", "admin", "administrative", "discovery") or (
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
    """A column by its key as an author reads it, as 'I/O' of 'i_o'"""

    return {"i_o": "I/O", "om": "O/M"}.get(column, column.replace("_", " "))


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
            if kinds is None or column in prose or not text.strip():
                continue
            typed = typed_of(text)
            if typed and typed.kind in kinds | COMMON:
                entry.typed[column] = typed
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
    return Entry(
        value=entry.get(key, ""),
        value_column=key,
        name=entry.get(name_key) if name_key else None,
        description=entry.get("description", ""),
        columns={
            k: v for k, v in entry.items() if k not in (key, name_key, "description")
        },
    )


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
                yield int(match["hex"], 16), name, entry.columns, values.source


REGEX_FEATURE_SECTION = re.compile(r"\(Feature Identifier ([0-9A-F]+)h\)$")


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
    for identifier, name, columns, source in identified(
        document, "feature_name", "feature_identifiers"
    ):
        if identifier in seen:
            continue
        seen[identifier] = alias(name)
        document.features[alias(name)] = Feature(
            identifier=identifier, name=name, columns=columns, source=source
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
            match = REGEX_FEATURE_SECTION.search(dwords.source.section_title or "")
            feature = by_identifier.get(int(match[1], 16)) if match else None
            if feature is None:
                left[key].append(dwords)
                continue
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
    """The log pages of the log page identifier tables, with the structure
    laying out each: the log page's own figure before a data structure, the
    first figure before later ones"""

    candidates = sorted(
        (s for s in document.structures if s.kind in ("log_page", "data_structure")),
        key=lambda s: (s.kind != "log_page", s.source.document, s.source.figure_nr),
    )
    for identifier, name, columns, source in identified(
        document, "log_page_name", "log_page_identifiers"
    ):
        key = alias(re.sub(r"\s+Log Page$", "", name, flags=re.IGNORECASE))
        if key in document.log_pages:
            continue
        wanted = log_page_key(name)
        structure = next(
            (s for s in candidates if log_page_key(s.name) == wanted), None
        ) or next(
            (s for s in candidates if names_match(log_page_key(s.name), wanted)),
            None,
        )
        document.log_pages[key] = LogPage(
            identifier=identifier,
            name=name,
            columns=columns,
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
                    s.name
                    for s in document.structures
                    if alias(s.name).startswith(alias(directive))
                    and alias(name) in alias(s.name)
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


def value_names(entry: "Entry") -> List[str]:
    """The name a value of a field goes by, as a list of none or one: its name,
    else the text of the first column naming it, as "management_operation"
    does; the heading the value is under is no name of it"""

    if entry.name:
        return [entry.name]
    skip = {"reference", "om", "description", "refer_to_section", "section"}
    return [
        text
        for column, text in entry.columns.items()
        if column not in skip and text and not typed_of(text)
    ][:1]


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


def link_structures(document: SpecDocument) -> None:
    """
    Set 'structure' on each field that has no subfields and whose description
    refers to the figure of a structure in the same document, for example
    LBAF0 of Identify Namespace, "defined in Figure 125". Of the structures
    referred to, the field is linked to the one as wide as the field: the
    description of LBAF0 also refers to Figure 127, which is wider. An entry
    of an array that refers to no such figure is linked to the one structure,
    as wide as the entry, whose name appears in its description, for example
    "an I/O Command Set Vector". All entries of an array get the structure
    that any of them has. A structure that lays out the entries of an array
    becomes a data structure whatever its caption says, and uncovered() then
    checks its fields for gaps.
    """

    structures = {
        (s.source.document, s.source.figure_nr): s for s in document.structures
    }
    widths = {key: bits_wide(structure) for key, structure in structures.items()}

    def laying_out(field: Bits, source: Source) -> Optional[Source]:
        size = field.array.stride if field.array else field.width
        bits = (size or 0) * (8 if field.unit == "bytes" else 1)
        named = [
            (source.document, int(number))
            for number in dict.fromkeys(REGEX_FIGURE.findall(field.description))
            if int(number) != source.figure_nr
        ]
        found = [key for key in named if key in widths and widths[key] == bits]
        if not found and field.array:
            text = f" {alias(field.description).replace('_', ' ')} "
            found = [
                key
                for key, structure in structures.items()
                if key[0] == source.document
                and key[1] != source.figure_nr
                and widths[key] == bits
                and "_" in alias(structure.name)
                and f" {alias(structure.name).replace('_', ' ')} " in text
            ]
        return structures[found[0]].source if len(found) == 1 else None

    def link(fields: List[Bits], source: Source) -> None:
        arrays: Dict[Tuple[str, int], List[Bits]] = {}
        for field in fields:
            field.structure = None
            if field.role == "field" and not field.fields:
                field.structure = laying_out(field, source)
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
    for key, described in document.dwords.items():
        cqe = key.startswith("cqe:")
        for command in by_name.get(key.removeprefix("cqe:"), []):
            for dwords in described:
                add_dwords(command.cqe if cqe else command.sqe, dwords)
            used.add(key)

    document.features, document.log_pages = {}, {}
    # The operations take their dwords before the looser matching of features
    link_directives(document, used)
    link_operations(document, used)
    link_features(document, used)
    link_structures(document)
    link_log_pages(document)
    link_values(document)

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
    unnamed.
    """

    for values in document.values:
        cited: Dict[int, Tuple[str, str]] = {}
        labels: Dict[str, int] = {}
        for i, entry in enumerate(values.entries):
            number = entry.columns.get("reference", "").strip()
            if REGEX_SECTION_NUMBER.match(number) and number in sections:
                cited[i] = (number, sections[number])
                match = REGEX_TITLE_CODE.search(sections[number])
                if match:
                    labels[match["label"]] = labels.get(match["label"], 0) + 1
        label = max(labels, key=lambda k: labels[k]) if labels else None
        by_code = {
            int(match["code"][:-1], 16): title
            for title in sections.values()
            for match in [REGEX_TITLE_CODE.search(title)]
            if match and match["label"] == label
        }
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
                if match and int(match["code"][:-1], 16) != code_value(entry.value):
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
            if title:
                entry.name = REGEX_TITLE_CODE.sub("", title)


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
        document.documents[document.meta.stem] = document.meta.model_copy()
        for figure in normalized.figures:
            add_figure(document, figure, document.meta.stem)
        name_by_sections(document, normalized.sections)
        document.errata += noted_errata(normalized, document.meta.stem)
        return resolve(document), []


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
        for key, command_set in document.command_sets.items():
            into = merged.command_sets.setdefault(
                key, CommandSet(name=command_set.name)
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
    merged = resolve(merged)
    hashes = [meta.sha256 for meta in merged.documents.values()]
    if hashes and all(hashes):
        merged.meta.input_sha256 = senfd.identity.input_sha256(h for h in hashes if h)
        merged.meta.combined_sha256 = senfd.identity.combined_sha256(
            merged.meta.input_sha256, merged.meta.senfd_sha256
        )
    return merged
