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

from pydantic import BaseModel, Field

from senfd.documents.base import Converter, Document, strip_all_suffixes
from senfd.documents.normalized import (
    Layout,
    LayoutField,
    NormalizedFigure,
    NormalizedFigureDocument,
)
from senfd.errors import Error
from senfd.normalize import Diagnostic, warning


class Source(BaseModel):
    """The document and the figure something came from"""

    document: str
    figure_nr: int


class Bits(BaseModel):
    """
    A field of bits or bytes; 'upper' and 'lower' are None where the document
    gives the range by a formula, which 'range' then holds
    """

    name: Optional[str] = None
    acronym: Optional[str] = None
    unit: str
    upper: Optional[int] = None
    lower: Optional[int] = None
    range: str
    description: str = ""
    section: Optional[str] = None
    columns: Dict[str, str] = Field(default_factory=dict)
    fields: List["Bits"] = Field(default_factory=list)


class Dwords(BaseModel):
    """The dwords 'lower' to 'upper' of a command, and their fields"""

    lower: int
    upper: int
    condition: Optional[str] = None
    fields: List[Bits] = Field(default_factory=list)
    source: Source


class Command(BaseModel):
    name: str
    opcode: int
    sqe: List[Dwords] = Field(default_factory=list)
    cqe: List[Dwords] = Field(default_factory=list)
    columns: Dict[str, str] = Field(default_factory=dict)
    source: Source


class CommandSet(BaseModel):
    name: str
    commands: Dict[str, Command] = Field(default_factory=dict)


class Structure(BaseModel):
    """
    A layout of fields that is no command's dwords: a data structure, a log
    page, a register or anything else a figure lays out
    """

    name: str
    kind: str
    unit: str
    qualifier: Optional[str] = None
    offset: Optional[str] = None
    fields: List[Bits] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    source: Source


class Entry(BaseModel):
    """A row of a table of values, as a status value or a log page identifier"""

    value: str
    name: Optional[str] = None
    description: str = ""
    columns: Dict[str, str] = Field(default_factory=dict)


class Values(BaseModel):
    """A table of values, by the kind of its caption and what it names"""

    kind: str
    name: Optional[str] = None
    qualifier: Optional[str] = None
    columns: List[str] = Field(default_factory=list)
    entries: List[Entry] = Field(default_factory=list)
    source: Source


class Feature(BaseModel):
    """A feature, by its identifier, and the dwords of the commands setting and
    getting it that are described for it"""

    identifier: int
    name: str
    columns: Dict[str, str] = Field(default_factory=dict)
    sqe: List[Dwords] = Field(default_factory=list)
    cqe: List[Dwords] = Field(default_factory=list)
    source: Source


class LogPage(BaseModel):
    """A log page, by its identifier, and the structure laying it out"""

    identifier: int
    name: str
    columns: Dict[str, str] = Field(default_factory=dict)
    structure: Optional[Structure] = None
    source: Source


class SpecDocument(Document):
    SUFFIX_JSON: ClassVar[str] = ".spec.document.json"
    SUFFIX_HTML: ClassVar[str] = ".spec.document.html"

    FILENAME_SCHEMA: ClassVar[str] = "spec.document.schema.json"
    FILENAME_HTML_TEMPLATE: ClassVar[str] = "spec.document.html.jinja2"

    command_sets: Dict[str, CommandSet] = Field(default_factory=dict)
    # Dwords of commands no opcode table of the document lists
    dwords: Dict[str, List[Dwords]] = Field(default_factory=dict)
    features: Dict[str, Feature] = Field(default_factory=dict)
    log_pages: Dict[str, LogPage] = Field(default_factory=dict)
    structures: List[Structure] = Field(default_factory=list)
    values: List[Values] = Field(default_factory=list)
    diagnostics: List[Diagnostic] = Field(default_factory=list)


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
        fields=[
            bits_of(nested_field, nested.unit)
            for nested in field.layouts
            for nested_field in nested.fields
        ],
    )


def fields_of(layout: Layout) -> List[Bits]:
    return [bits_of(field, layout.unit) for field in layout.fields]


# The dwords of the pointers, where the common command format puts them; their
# figures do not say
POINTERS = {"metadata_pointer": (4, 5), "data_pointer": (6, 9)}


def add_figure(document: SpecDocument, figure: NormalizedFigure, stem: str) -> None:
    source = Source(document=stem, figure_nr=figure.figure_nr)
    subject = figure.subject

    if figure.shape == "opcode" and subject.kind == "opcodes" and subject.name:
        set_name = command_set_name(subject.name)
        command_set = document.command_sets.setdefault(
            alias(set_name), CommandSet(name=set_name)
        )
        for entry in figure.entries:
            match = REGEX_HEX.match(entry.get("opcode", ""))
            name = without_footnote(entry.get("command", ""))
            if not match or not name:
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
        if figure.shape in ("value", "requirement") and figure.entries:
            document.values.append(
                Values(
                    kind=subject.kind,
                    name=subject.name,
                    qualifier=subject.qualifier,
                    columns=figure.columns,
                    entries=[entry_of(entry) for entry in figure.entries],
                    source=source,
                )
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
        document.dwords.setdefault(key, []).append(
            Dwords(
                lower=dwords[0],
                upper=dwords[1],
                condition=subject.condition,
                fields=fields_of(figure.layout),
                source=source,
            )
        )
        return

    document.structures.append(
        Structure(
            name=subject.name or figure.caption,
            kind=subject.kind,
            unit=figure.layout.unit,
            qualifier=subject.qualifier,
            offset=subject.offset,
            fields=fields_of(figure.layout),
            notes=figure.layout.notes,
            source=source,
        )
    )


def entry_of(entry: Dict[str, str]) -> Entry:
    """An entry by its value, whichever column holds it"""

    keys = ("value", "cns_value", "identifier", "command", "name")
    key = next((k for k in keys if entry.get(k)), next(iter(entry), ""))
    names = [k for k in ("name", "log_page_name", "feature_name") if k != key]
    name_key = next((k for k in names if entry.get(k)), None)
    return Entry(
        value=entry.get(key, ""),
        name=entry.get(name_key) if name_key else None,
        description=entry.get("description", ""),
        columns={
            k: v for k, v in entry.items() if k not in (key, name_key, "description")
        },
    )


def add_dwords(have: List[Dwords], dwords: Dwords) -> None:
    """Add 'dwords' to 'have', unless the same dwords are there already"""

    key = (dwords.lower, dwords.upper, dwords.condition)
    if all((d.lower, d.upper, d.condition) != key for d in have):
        have.append(dwords)


def assign_dwords(document: SpecDocument) -> None:
    """Give the commands of the command sets the dwords described for them"""

    for key in list(document.dwords):
        cqe = key.startswith("cqe:")
        name = key.removeprefix("cqe:")
        commands = [
            command_set.commands[name]
            for command_set in document.command_sets.values()
            if name in command_set.commands
        ]
        if not commands:
            continue
        for command in commands:
            have = command.cqe if cqe else command.sqe
            for dwords in document.dwords[key]:
                add_dwords(have, dwords)
        del document.dwords[key]


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
        for figure in normalized.figures:
            add_figure(document, figure, document.meta.stem)
        assign_dwords(document)
        return document, []


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


def link_features(document: SpecDocument) -> None:
    """The features of the feature identifier tables, with the dwords described
    for each, which the captions name by the feature"""

    for identifier, name, columns, source in identified(
        document, "feature_name", "feature_identifiers"
    ):
        key = alias(name)
        feature = document.features.setdefault(
            key,
            Feature(identifier=identifier, name=name, columns=columns, source=source),
        )
        for dwords in document.dwords.pop(key, []):
            add_dwords(feature.sqe, dwords)
        for dwords in document.dwords.pop(f"cqe:{key}", []):
            add_dwords(feature.cqe, dwords)


def link_log_pages(document: SpecDocument) -> None:
    """The log pages of the log page identifier tables, with the structure of
    each, which a log page's caption names"""

    structures = {alias(s.name): s for s in document.structures if s.kind == "log_page"}
    for identifier, name, columns, source in identified(
        document, "log_page_name", "log_page_identifiers"
    ):
        key = alias(re.sub(r"\s+Log Page$", "", name, flags=re.IGNORECASE))
        document.log_pages.setdefault(
            key,
            LogPage(
                identifier=identifier,
                name=name,
                columns=columns,
                structure=structures.get(key),
                source=source,
            ),
        )


def merge(documents: List[SpecDocument]) -> SpecDocument:
    """
    One document of 'documents': a command set listed by more than one is one
    command set, and a command gets the dwords another document describes
    """

    merged = SpecDocument()
    merged.meta.stem = "merged"
    for document in documents:
        for key, command_set in document.command_sets.items():
            into = merged.command_sets.setdefault(
                key, CommandSet(name=command_set.name)
            )
            for name, command in command_set.commands.items():
                existing = into.commands.setdefault(name, command)
                if existing is command:
                    continue
                for dwords in command.sqe:
                    add_dwords(existing.sqe, dwords)
                for dwords in command.cqe:
                    add_dwords(existing.cqe, dwords)
        for key, described in document.dwords.items():
            merged.dwords.setdefault(key, []).extend(described)
        merged.structures += document.structures
        merged.values += document.values
        merged.diagnostics += document.diagnostics

    assign_dwords(merged)

    # A command of the same name in two command sets is the same command, as
    # the reservation commands that the base specification describes and the
    # NVM command set lists; each gets the dwords of the other
    by_name: Dict[str, List[Command]] = {}
    for command_set in merged.command_sets.values():
        for name, command in command_set.commands.items():
            by_name.setdefault(name, []).append(command)
    for commands in by_name.values():
        for command in commands:
            for other in commands:
                for dwords in other.sqe:
                    add_dwords(command.sqe, dwords)
                for dwords in other.cqe:
                    add_dwords(command.cqe, dwords)

    link_features(merged)
    link_log_pages(merged)

    for key, unassigned in merged.dwords.items():
        for d in unassigned:
            merged.diagnostics.append(
                warning(
                    "dwords-without-command",
                    f"Dwords {d.lower}:{d.upper} of '{key}', "
                    f"{d.source.document} figure {d.source.figure_nr}, "
                    "of no command of an opcode table",
                )
            )
    return merged
