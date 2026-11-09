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
from typing import ClassVar, Dict, List, Optional, Tuple

from pydantic import Field

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
from senfd.normalize import Diagnostic, note, warning


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


class Bits(Model):
    """
    A field of bits or bytes; 'upper' and 'lower' are None where the document
    gives the range by a formula, which 'range' then holds
    """

    name: Optional[str] = None
    """The name of the field, as 'Force Unit Access'"""
    acronym: Optional[str] = None
    """Its acronym, as "FUA"; None where it has none or the document's is not
    one, which is then an erratum"""
    unit: str
    """What the range counts: "bits" or 'bytes'"""
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
    columns: Dict[str, str] = Field(default_factory=dict)
    """The figure's other columns of the field, by their keys, as "reset" or
    'type'"""
    fields: List["Bits"] = Field(default_factory=list)
    """The fields within this one, as its description lays them out"""
    union: Optional[int] = None
    """Of fields sharing bits, the union of the layout they are of"""
    alternative: Optional[int] = None
    """Of fields sharing bits, which fields go together, as an IPv4 address
    and the reserved bits after it, against an IPv6 address of the same
    bytes"""
    values: List["Entry"] = Field(default_factory=list)
    """The values the field takes, as the table in its description gives
    them"""


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
    kind: str
    """What its caption says it is, as "data_structure", "log_page" or
    "register", or 'other'"""
    unit: str
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


class Typed(Model):
    """
    A value of a table as what it is: a requirement "level" (M, O, P, NR, R),
    a yes or no "flag", an "identifier" or a range of them, a "note" it is
    given by, a "reference" to another specification, or "reserved" or
    "vendor_specific"; with the footnotes marked on it
    """

    kind: str
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

    kind: str
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


class Erratum(Model):
    """
    Something of a figure that is not what its kind of value must be, as a
    range beyond the dword it is of, left out of the model; or fields that do
    not fit together, as two of the same bits, which the model keeps. Each is
    a candidate erratum of the specification, saying where it is.
    """

    code: str
    """What kind it is, as "value", "acronym", "range-outside",
    "range-reversed", "opcode" or 'gap'"""
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


def bits_of(field: LayoutField, unit: str) -> Bits:
    return Bits(
        name=field.name,
        acronym=field.acronym,
        unit=unit,
        upper=field.range.upper,
        lower=field.range.lower,
        range=field.range.text,
        description=field.description,
        section=field.section,
        columns=field.columns,
        fields=unions_of(
            [
                bits_of(nested_field, nested.unit)
                for nested in field.layouts
                for nested_field in nested.fields
            ]
        ),
        values=[value_of(entry) for entry in field.values],
    )


def value_of(entry: Dict[str, str]) -> "Entry":
    """A value a field takes, its value typed where it has a form, as "000b",
    "1h" or "2" """

    value = entry_of(entry)
    typed = typed_of(value.value)
    if typed:
        value.typed[value.value_column] = typed
    return value


def fields_of(layout: Layout) -> List[Bits]:
    fields = unions_of([bits_of(field, layout.unit) for field in layout.fields])
    number_unions(fields)
    return fields


def same_structure(a: Bits, b: Bits) -> bool:
    """Whether fields are of one structure, as a table listing the fields of
    several, by a column naming the structure of each, gives fields of others"""

    for column in set(a.columns) & set(b.columns):
        if "structure" in column and a.columns[column] != b.columns[column]:
            return False
    return True


def number_unions(fields: List[Bits], start: int = 0) -> int:
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


def unions_of(fields: List[Bits]) -> List[Bits]:
    """
    'fields' with those sharing bits, of a section, made alternatives of a
    union: the fields of bits some other shares are a region, and each is,
    in the order of the table, of the first alternative of its region whose
    fields it shares no bits with
    """

    def overlaps(a: Bits, b: Bits) -> bool:
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
        regions: List[List[Bits]] = []
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
            alternatives: List[List[Bits]] = []
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
    fields: List[Bits], width: Optional[int], source: Source
) -> Tuple[List[Bits], List[Erratum]]:
    """
    The fields of a layout that are what fields must be, and the errata of
    those that are not: an acronym that is not one is left out, and a field of
    reversed bounds, or beyond the 'width' of the dwords it is of, is left out
    whole; fields sharing bits are not errata, as a layout can give either of
    two, as an IPv4 or an IPv6 address
    """

    errata: List[Erratum] = []
    kept: List[Bits] = []
    for field in fields:
        what = f"{field.range} {field.name or ''}".strip()
        if field.acronym and not REGEX_ACRONYM.match(field.acronym):
            errata.append(
                Erratum(
                    code="acronym",
                    message=f"Field {what}: acronym '{field.acronym}' is not one",
                    found=field.acronym,
                    source=source,
                )
            )
            field = field.model_copy(update={"acronym": None})
        if field.upper is not None and field.lower is not None:
            if field.upper < field.lower:
                errata.append(
                    Erratum(
                        code="range-reversed",
                        message=f"Field {what}: upper bound below the lower",
                        found=field.range,
                        source=source,
                    )
                )
                continue
            if width is not None and field.unit == "bits" and field.upper >= width:
                errata.append(
                    Erratum(
                        code="range-outside",
                        message=(
                            f"Field {what}: bit {field.upper} beyond the "
                            f"{width} bits of its dwords"
                        ),
                        found=field.range,
                        source=source,
                    )
                )
                continue
        nested, nested_errata = checked(field.fields, None, source)
        errata += nested_errata
        kept.append(field.model_copy(update={"fields": nested}))

    return kept, errata


def add_figure(document: SpecDocument, figure: NormalizedFigure, stem: str) -> None:
    source = Source(
        document=stem,
        figure_nr=figure.figure_nr,
        page_nr=figure.page_nr,
        pdf_page=figure.pdf_page,
        section=figure.section,
        section_title=figure.section_title,
    )
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
            document.values.append(
                Values(
                    kind=subject.kind,
                    name=subject.name,
                    qualifier=subject.qualifier,
                    scope=subject.scope,
                    columns=figure.columns,
                    entries=[entry_of(entry) for entry in figure.entries],
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
        fields, errata = checked(
            fields_of(figure.layout), 32 * (dwords[1] - dwords[0] + 1), source
        )
        document.errata += errata
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

    fields, errata = checked(fields_of(figure.layout), None, source)
    document.errata += errata
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
TYPED_FORMS = [
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
]
# The forms any typed column can hold besides its own
COMMON = {"note", "reference", "reserved", "vendor_specific"}


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


def entry_of(entry: Dict[str, str]) -> Entry:
    """An entry by its value, whichever column holds it"""

    keys = ("value", "cns_value", "identifier")
    key = next(
        (k for k in keys if entry.get(k)),
        next(
            (k for k in entry if k.endswith("_value") and entry[k]),
            next(
                (k for k in ("command", "name") if entry.get(k)), next(iter(entry), "")
            ),
        ),
    )
    names = [k for k in entry if k == "name" or (k.endswith("_name") and k != key)]
    name_key = next((k for k in names if entry.get(k)), None)
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

    # The exact name first, then the looser matches, so that "Asynchronous
    # Event Configuration" is not taken by a feature it merely starts with
    for exact in (True, False):
        for key, described in document.dwords.items():
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
            name = entry.columns.get("directive", "")
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

    for ident, claimed in claims.items():
        key, described = described_by[ident]
        if len({id(c[0]) for c in claimed}) > 1:

            def nearness(claim: Claim) -> int:
                return shared_prefix(claim[4].source.section, described.source.section)

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
    link_log_pages(document)

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

    document.unassigned = {
        key: described for key, described in document.dwords.items() if key not in used
    }
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
    return resolve(merged)
