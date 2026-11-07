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
from senfd.normalize import Diagnostic, note, warning


class Source(BaseModel):
    """Where something came from: the document, the figure, the page the
    figure is on, and the section it is in, by number and title"""

    document: str
    figure_nr: int
    page_nr: Optional[int] = None
    section: Optional[str] = None
    section_title: Optional[str] = None


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
    qualifier: Optional[str] = None
    fields: List[Bits] = Field(default_factory=list)
    source: Source


class Operation(BaseModel):
    """
    What a command does for the values of its selecting fields, as a directive
    operation of Directive Receive by its directive type (DTYPE) and operation
    (DOPER), with the dwords and the structures of that operation
    """

    name: str
    selectors: Dict[str, int] = Field(default_factory=dict)
    sqe: List[Dwords] = Field(default_factory=list)
    cqe: List[Dwords] = Field(default_factory=list)
    structures: List[str] = Field(default_factory=list)
    source: Source


class Command(BaseModel):
    name: str
    opcode: int
    sqe: List[Dwords] = Field(default_factory=list)
    cqe: List[Dwords] = Field(default_factory=list)
    operations: List[Operation] = Field(default_factory=list)
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

    # What the figures describe: the commands of the opcode tables, the dwords
    # by the name their captions give, the structures and the tables of values
    command_sets: Dict[str, CommandSet] = Field(default_factory=dict)
    dwords: Dict[str, List[Dwords]] = Field(default_factory=dict)
    structures: List[Structure] = Field(default_factory=list)
    values: List[Values] = Field(default_factory=list)

    # What resolve() makes of them: the dwords and operations of the commands,
    # the features and log pages, and the dwords of none of them
    features: Dict[str, Feature] = Field(default_factory=dict)
    log_pages: Dict[str, LogPage] = Field(default_factory=dict)
    unassigned: Dict[str, List[Dwords]] = Field(default_factory=dict)
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
    source = Source(
        document=stem,
        figure_nr=figure.figure_nr,
        page_nr=figure.page_nr,
        section=figure.section,
        section_title=figure.section_title,
    )
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
                    columns=figure.columns,
                    entries=[entry_of(entry) for entry in figure.entries],
                    source=source,
                )
            )
        else:
            document.diagnostics.append(
                note(
                    "figure-not-modelled",
                    f"{stem} figure {figure.figure_nr}, a table of no shape senfd "
                    f"models: '{figure.caption}'",
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
                qualifier=subject.qualifier,
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
    link_features(document, used)
    link_log_pages(document)

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
                    f"Dwords {d.lower}:{d.upper} of '{key}', {d.source.document} "
                    f"figure {d.source.figure_nr}, of no command, feature or "
                    "directive operation",
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
        merged.diagnostics += [
            d for d in document.diagnostics if d.code != "dwords-unassigned"
        ]
    return resolve(merged)
