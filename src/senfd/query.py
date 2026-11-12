# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
Answers to questions about the specification, from its merged data model

Each answer is a few lines of text, saying the figure of the document it came
from, so that it can be checked against the specification. Given 'markdown',
the fields of an answer are a table of them instead, for an answer shown to a
reader rather than read by an agent. The data model is the
merged specification document that senfd writes, by default in the cache:

    senfd *.docx --output ~/.cache/senfd
    sate command write 12
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from senfd.documents.spec import value_names as senfd_value_names
from senfd.documents.spec import (
    linked,
    Bits,
    Command,
    Dwords,
    Entry,
    Source,
    SpecDocument,
    Structure,
    Values,
    alias,
    cite,
    document_name,
    dwords_named,
)


def default_spec_path() -> Path:
    if os.environ.get("SENFD_SPEC"):
        return Path(os.environ["SENFD_SPEC"])
    cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return cache / "senfd" / "merged.spec.document.json"


def load(path: Optional[Path] = None) -> SpecDocument:
    path = path or default_spec_path()
    return SpecDocument.model_validate_json(path.read_text(encoding="utf-8"))


def bits(field: Bits) -> str:
    rng = field.range  # As the document writes it
    acronym = f" ({field.acronym})" if field.acronym else ""
    # Fields sharing bits are alternatives, "either" of a union
    either = (
        f" [union {field.union}, alternative {field.alternative}]"
        if field.union is not None
        else ""
    )
    return f"{rng} {field.name or ''}{acronym}{either}"


def joined(description: str) -> str:
    """'description' on one line, whatever lines a column of a PDF broke it
    over; a hyphen ending a line stays, and joins the words beside it"""

    return " ".join(re.sub(r"-\s*\n\s*", "-", description).split())


def lines_of_fields(
    fields: List[Bits], verbose: bool, indent: str = "  "
) -> Iterable[str]:
    section = None
    for field in fields:
        if field.section != section and field.section:
            yield f"{indent}[{field.section}]"
        section = field.section
        yield indent + bits(field)
        if verbose and field.description:
            yield indent + "  " + joined(field.description)
        if verbose:
            for value in field.values:
                # The name, else the start of the description, for reading
                name = (senfd_value_names(value) or [value.description[:60]])[0]
                yield f"{indent}    = {value.value} {name}".rstrip()
            if field.values_in:
                yield f"{indent}    values in [{cite(field.values_in)}]"
            for told in array_and_structure(field):
                yield f"{indent}    {told}"
        if field.fields:
            yield from lines_of_fields(field.fields, verbose, indent + "    ")


def array_and_structure(field: Bits) -> List[str]:
    """What the data model says of 'field' as an entry of an array and of
    the structure laying it out, a line of each, as "entry 0 of 64, each of
    4 bytes" and "laid out in [NVM 1.3, Figure 125]" """

    told = []
    if field.array:
        index = (
            "last entry" if field.array.index is None else f"entry {field.array.index}"
        )
        count = field.array.count or "as many as the data says"
        told.append(f"{index} of {count}, each of {field.array.stride} {field.unit}")
    if field.structure:
        told.append(f"laid out in [{cite(field.structure)}]")
    return told


def structure_of(spec: SpecDocument, field: Bits) -> Optional[Structure]:
    """The structure laying out 'field' that the data model links the field
    to, as the LBA Format of LBAF0 of Identify Namespace, or None"""

    if field.structure is None:
        return None
    return next((s for s in spec.structures if s.source == field.structure), None)


def cell(text: str) -> str:
    """'text' as one cell of a Markdown table"""

    return " ".join(text.split()).replace("|", "\\|")


def units_within(fields: List[Bits], unit: str) -> List[str]:
    """The units of the fields within 'fields' that are not 'unit', as the
    bits of a byte in a table of bytes, in the order met"""

    found: List[str] = []
    for field in fields:
        if field.unit != unit and field.unit not in found:
            found.append(field.unit)
        for within in units_within(field.fields, unit):
            if within not in found:
                found.append(within)
    return found


def table_of_fields(fields: List[Bits], verbose: bool, unit: str = "bits") -> List[str]:
    """The fields as a Markdown table; a field within another is named by both
    acronyms, as "PRINFO.PRACT". Where fields within others are of another
    unit, as the bits of a byte in a table of bytes, that unit is a column of
    its own, beside the table's, and a field's range stands in the column of
    its unit, the other left empty: the bits of a byte read under Bits with
    nothing under Bytes. A heading of fields is a row of its own."""

    units = [unit] + units_within(fields, unit)
    head = [u.title() for u in units] + ["Name", "Acronym"]
    head += ["Description"] if verbose else []
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]

    def rows(fields: List[Bits], parent: str) -> Iterable[str]:
        section = None
        for field in fields:
            if field.section != section and field.section:
                cells = [""] * len(head)
                cells[len(units)] = "**" + cell(field.section) + "**"
                yield "| " + " | ".join(cells) + " |"
            section = field.section
            acronym = field.acronym or ""
            path = f"{parent}.{acronym}" if parent and acronym else acronym
            either = (
                f" (union {field.union}, alternative {field.alternative})"
                if field.union is not None
                else ""
            )
            where = ["" for _ in units]
            where[units.index(field.unit) if field.unit in units else 0] = field.range
            row = where + [cell((field.name or "") + either), cell(path)]
            if verbose:
                text = joined(field.description or "")
                values = [
                    f"{v.value} {(senfd_value_names(v) or [v.description[:60]])[0]}"
                    for v in field.values
                ]
                if values:
                    text += " Values: " + ", ".join(values)
                if field.values_in:
                    text += f" Values in [{cite(field.values_in)}]"
                for told in array_and_structure(field):
                    text += f" {told[0].upper()}{told[1:]}."
                row.append(cell(text))
            yield "| " + " | ".join(row) + " |"
            yield from rows(field.fields, path or parent)

    lines += rows(fields, "")
    return lines


def dword_label(dwords: Dwords, prefix: str) -> str:
    span = (
        f"{prefix}{dwords.lower}"
        if dwords.lower == dwords.upper
        else f"{prefix}{dwords.lower}-{dwords.upper}"
    )
    condition = f" if {dwords.condition}" if dwords.condition else ""
    qualifier = f", {dwords.qualifier}" if dwords.qualifier else ""
    return f"{span}{condition}{qualifier} [{cite(dwords.source)}]"


def lines_of_dwords(
    dwords: List[Dwords],
    prefix: str,
    dword: Optional[int],
    verbose: bool,
    markdown: bool = False,
) -> Iterable[str]:
    for d in sorted(dwords, key=lambda d: (d.lower, d.condition or "")):
        if dword is not None and not d.lower <= dword <= d.upper:
            continue
        if markdown:
            yield ""
            yield f"**{dword_label(d, prefix)}**"
            yield ""
            yield from table_of_fields(d.fields, verbose)
        else:
            yield dword_label(d, prefix)
            yield from lines_of_fields(d.fields, verbose)


def find(names: Iterable[str], text: str) -> List[str]:
    """The keys among 'names' that are 'text', else those containing it"""

    key = alias(text)
    names = list(names)
    if key in names:
        return [key]
    return [name for name in names if key in name]


def command(
    spec: SpecDocument,
    name: str,
    dword: Optional[int] = None,
    verbose=False,
    markdown=False,
) -> List[str]:
    if not name.strip():
        return ["Give the name of a command"]
    lines = []
    opcode = re.fullmatch(r"(?:0x)?([0-9A-Fa-f]{1,2})h?", name.strip())
    found = [
        (command_set, key)
        for command_set in spec.command_sets.values()
        for key in (
            # A command by its opcode, "8Ch", in every command set having it
            [
                k
                for k, c in command_set.commands.items()
                if c.opcode == int(opcode[1], 16)
            ]
            if opcode and re.search(r"h$|^0x|\d", name.strip())
            else find(command_set.commands, name)
        )
    ]
    # A command of the name given rather than those whose names contain it
    exact = [(cs, key) for cs, key in found if key == alias(name)]
    for command_set, key in exact or found:
        cmd: Command = command_set.commands[key]
        title = (
            f"{cmd.name}: {command_set.name} command, opcode {cmd.opcode:02X}h "
            f"[{cite(cmd.source)}]"
        )
        lines.append(f"### {title}" if markdown else title)
        before = len(lines)
        lines += lines_of_dwords(cmd.sqe, "cdw", dword, verbose, markdown)
        if dword is None:
            lines += lines_of_dwords(cmd.cqe, "cqe dw", None, verbose, markdown)
        elif len(lines) == before and not cmd.operations:
            lines.append(f"No figure describes cdw{dword} of {cmd.name}")
        for operation in cmd.operations:
            selectors = " ".join(
                f"{k}={v:02X}h" for k, v in operation.selectors.items()
            )
            title = (
                f"operation {operation.name}, {selectors} [{cite(operation.source)}]"
            )
            lines += ["", f"#### {title}"] if markdown else [title]
            lines += lines_of_dwords(operation.sqe, "cdw", dword, verbose, markdown)
            if dword is None:
                lines += lines_of_dwords(
                    operation.cqe, "cqe dw", None, verbose, markdown
                )
                lines += [f"  returns {name}" for name in operation.structures]
    return lines or [f"No command '{name}'"]


def by_identifier_or_name(items: dict, key: str) -> list:
    """The items of identifier 'key', hexadecimal as the specification writes
    identifiers, "12", "12h" and "0x12" alike, else those of name 'key'"""

    match = re.fullmatch(r"(?:0x)?([0-9A-Fa-f]{1,2})h?", key.strip())
    if match:
        identifier = int(match[1], 16)
        found = [item for item in items.values() if item.identifier == identifier]
        if found:
            return found
    return [items[k] for k in find(items, key)]


def feature(spec: SpecDocument, key: str, verbose=False, markdown=False) -> List[str]:
    lines = []
    for f in by_identifier_or_name(spec.features, key):
        title = f"{f.identifier:02X}h {f.name} [{cite(f.source)}]"
        lines.append(f"### Feature {title}" if markdown else title)
        lines += lines_of_dwords(f.sqe, "cdw", None, verbose, markdown)
        lines += lines_of_dwords(f.cqe, "cqe dw", None, verbose, markdown)
    return lines or [f"No feature '{key}'"]


def log_page(spec: SpecDocument, key: str, verbose=False, markdown=False) -> List[str]:
    lines = []
    shown = set()
    for page in by_identifier_or_name(spec.log_pages, key):
        title = f"{page.identifier:02X}h {page.name} [{cite(page.source)}]"
        lines.append(f"### Log page {title}" if markdown else title)
        where = page.structure and (
            page.structure.source.document,
            page.structure.source.figure_nr,
        )
        if where and where in shown:
            lines.append(f"  laid out as above, {page.structure.name}")
        elif page.structure:
            shown.add(where)
            lines += lines_of_structure(page.structure, verbose, markdown)
        else:
            lines.append("  no figure laying it out is known")
    return lines or [f"No log page '{key}'"]


def lines_of_structure(
    structure: Structure, verbose: bool, markdown: bool = False
) -> List[str]:
    offset = f" at offset {structure.offset}" if structure.offset else ""
    title = f"{structure.name}{offset}, {structure.unit} [{cite(structure.source)}]"
    if markdown:
        lines = ["", f"**{title}**", ""]
        lines += table_of_fields(structure.fields, verbose, structure.unit)
    else:
        lines = [title]
        lines += lines_of_fields(structure.fields, verbose)
    lines += [f"  Note: {note[:160]}" for note in structure.notes if verbose]
    return lines


def structure(
    spec: SpecDocument, name: str, verbose=False, markdown=False
) -> List[str]:
    key = alias(name)
    if not key:
        return ["Give the name of a structure"]

    def exact(s: Structure) -> bool:
        # "Identify Controller" names "Identify - Identify Controller" too
        return key in (alias(s.name), alias(s.name.partition(" - ")[2]))

    def base_first(s: Structure) -> Tuple[bool, str]:
        document = document_name(s.source.document)
        return not document.startswith("Base "), document

    # Of the structures of the name given, and then of those whose names
    # contain it, the Base specification's before the command sets'
    named = sorted((s for s in spec.structures if exact(s)), key=base_first) + sorted(
        (s for s in spec.structures if key in alias(s.name) and not exact(s)),
        key=base_first,
    )
    if len(named) > 8:
        return [f"{len(named)} structures; be more specific:"] + [
            f"  {s.name} [{cite(s.source)}]" for s in named[:40]
        ]
    lines = []
    for s in named:
        lines += lines_of_structure(s, verbose, markdown)
    return lines or [f"No structure '{name}'"]


def search(
    spec: SpecDocument, text: str, limit: int = 40, verbose: bool = False
) -> List[str]:
    """Fields by acronym or name, and things by name, with where they are;
    with 'verbose', a field's description too, its first line"""

    needle = text.strip().lower()
    if not needle:
        return ["Give an acronym or a name to search for"]
    hits: List[str] = []

    def match(field: Bits) -> bool:
        return (field.acronym or "").lower() == needle or needle in (
            field.name or ""
        ).lower()

    def fields(where: str, items: List[Bits]):
        for field in items:
            if match(field):
                hit = f"{where}: {bits(field).strip()}"
                if verbose and field.description:
                    hit += ": " + field.description.split("\n")[0][:160]
                hits.append(hit)
            fields(where, field.fields)

    for command_set in spec.command_sets.values():
        for cmd in command_set.commands.values():
            if needle in cmd.name.lower():
                hits.append(
                    f"command {cmd.name}, opcode {cmd.opcode:02X}h [{cite(cmd.source)}]"
                )
            for d in cmd.sqe:
                fields(f"{cmd.name} {dword_label(d, 'cdw')}", d.fields)
            for d in cmd.cqe:
                fields(f"{cmd.name} {dword_label(d, 'cqe dw')}", d.fields)
    for f in spec.features.values():
        if needle in f.name.lower():
            hits.append(f"feature {f.identifier:02X}h {f.name} [{cite(f.source)}]")
        for d in f.sqe:
            fields(f"feature {f.name} {dword_label(d, 'cdw')}", d.fields)
        for d in f.cqe:
            fields(f"feature {f.name} {dword_label(d, 'cqe dw')}", d.fields)
    for key, unassigned in spec.unassigned.items():
        for d in unassigned:
            fields(f"{key} {dword_label(d, 'cdw')}", d.fields)
    for page in spec.log_pages.values():
        if needle in page.name.lower():
            hits.append(
                f"log page {page.identifier:02X}h {page.name} [{cite(page.source)}]"
            )
    for s in spec.structures:
        if needle in s.name.lower():
            hits.append(f"structure {s.name} [{cite(s.source)}]")
        fields(f"{s.name} [{cite(s.source)}]", s.fields)

    unique = list(dict.fromkeys(hits))
    if len(unique) > limit:
        return unique[:limit] + [f"... and {len(unique) - limit} more"]
    return unique or [f"Nothing named '{text}'"]


# The kinds of tables of values as a question names them; "status code type"
# before "status code", which it contains
VALUE_KINDS = [
    (r"status code types?|sct", "status_code_type"),
    (r"status(?: codes?| values?)?", "status_values"),
    (r"cns(?: values?)?", "cns_values"),
    (r"log ?page identifiers?", "log_page_identifiers"),
    (r"feature identifiers?", "feature_identifiers"),
]

# The words a value is asked with that name no table and no entry
ASKING = {"what", "which", "is", "are", "the", "a", "an", "of", "for", "in", "to"}


def table_title(table: Values, column: str = "") -> str:
    """A table of values as a question names it, as "Command Specific status
    code of Write", "Generic Command status code" or "CNS value of Identify";
    a table of other values by the header of 'column', the column of its
    codes, as "opcode of NVMe/TCP PDU Types", where that is not "value" """

    if table.kind == "status_values" and table.qualifier == "Status Code Type":
        return "Status Code Type (SCT)"
    kind = {
        "status_values": "status code",
        "cns_values": "CNS value",
        "log_page_identifiers": "log page identifier",
        "feature_identifiers": "feature identifier",
        "requirements": "requirement",
    }.get(table.kind, "value")
    if kind == "value" and column and column != "value":
        kind = column.replace("_", " ")
    parts = [table.qualifier, kind] if table.qualifier else [kind]
    if table.name and alias(table.name) != alias(kind):
        parts.append(f"of {table.name}")
    title = " ".join(parts)
    if table.scope and table.scope != table.name:
        title += f", {table.scope}"
    return title


def of_kind(table: Values, kind: str) -> bool:
    """Whether 'table' is of 'kind', the status code types being no status
    codes; every table is of the kind "" """

    types = table.kind == "status_values" and table.qualifier == "Status Code Type"
    if kind == "status_code_type":
        return types
    if kind == "status_values":
        return table.kind == "status_values" and not types
    return not kind or table.kind == kind


def tables_of_values(
    spec: SpecDocument, field: Bits, every: bool = False
) -> List[Values]:
    """The tables of the values of 'field' that the data model links the
    field to: the table of the figure that the description of the field
    names, as the CNS values of the Base specification for CNS of Identify.
    With 'every', the tables of the same kind of every document follow it,
    as the CNS values that each command set specification adds; a table of
    the kind "other" is alone of its kind."""

    if field.values_in is None:
        return []
    linked = [table for table in spec.values if table.source == field.values_in]
    if every and linked and linked[0].kind != "other":
        linked += [
            table
            for table in spec.values
            if table.kind == linked[0].kind and table not in linked
        ]
    return linked


def values_of_field(
    spec: SpecDocument, field: Bits, every: bool = False
) -> List[Entry]:
    """The values 'field' takes: those its own figure gives, else the entries
    of the tables that tables_of_values() finds for it"""

    if field.values:
        return list(field.values)
    return [e for table in tables_of_values(spec, field, every) for e in table.entries]


def within(written: str, value: int) -> bool:
    """Whether 'value' is the value 'written', as "82h", or in its range, as
    "C0h to FFh" """

    match = re.fullmatch(
        r"([0-9A-Fa-f]+)h(?:\s*(?:to|-)\s*([0-9A-Fa-f]+)h)?", written.strip()
    )
    if not match:
        return False
    low = int(match[1], 16)
    high = int(match[2], 16) if match[2] else low
    return low <= value <= high


def value(
    spec: SpecDocument,
    text: str,
    verbose=False,
    markdown=False,
    limit: int = 40,
    skip: Tuple[str, ...] = (),
) -> List[str]:
    """The entries of the tables of values 'text' asks for, each with its
    table and where it is: by the kind of table, as "status code", "status
    code type" or "CNS", by the value, as "82h" or "0x82", and by words of
    the entry's name or its table's, as "zone boundary error", all of which
    an entry found meets; of every kind where none is named. With 'verbose',
    an entry's description and its other columns too. The tables of the kinds
    in 'skip' are left out."""

    lower = " ".join(text.lower().split())
    kind = ""
    for pattern, of in VALUE_KINDS:
        match = re.search(rf"\b(?:{pattern})\b", lower)
        if match:
            kind = of
            lower = lower[: match.start()] + " " + lower[match.end() :]
            break
    wanted: Optional[int] = None
    whole = re.fullmatch(r"\s*(?:0x)?([0-9a-f]{1,2})h?\s*", lower)
    if whole:
        wanted, lower = int(whole[1], 16), ""
    else:
        match = re.search(r"\b(?:0x([0-9a-f]{1,2})|([0-9a-f]{1,2})h)\b", lower)
        if match:
            wanted = int(match[1] or match[2], 16)
            lower = lower[: match.start()] + " " + lower[match.end() :]
    words = [
        w for w in re.findall(r"[a-z0-9]+", lower) if len(w) > 1 and w not in ASKING
    ]
    if not kind and wanted is None and not words:
        return ["Give the kind of table, a value or a name, as 'status code 82h'"]

    def named(entry: Entry) -> str:
        """The entry by its name, and its acronym or symbol where a column of
        its own holds it, as "Foo Doorbell (Admin) (FOODBL)" """

        name = entry.name or entry.description.split("\n")[0][:160]
        mark = entry.columns.get("acronym") or entry.columns.get("symbol")
        return f"{name} ({mark})" if mark and mark not in name else name

    def has(word: str, text: str) -> bool:
        """Whether 'text' has 'word', or its plural, as "types" of "type" """

        return f" {word} " in text or f" {word}s " in text

    def spaced(text: str) -> str:
        return " " + " ".join(re.findall(r"[a-z0-9]+", text.lower())) + " "

    found = []
    for table in spec.values:
        if not of_kind(table, kind) or table.kind in skip:
            continue
        document = document_name(table.source.document)
        for entry in table.entries:
            if wanted is not None and not within(entry.value, wanted):
                continue
            titles = f"{table_title(table)} {table_title(table, entry.value_column)}"
            of_name = spaced(f"{titles} {document} {named(entry)}")
            if all(has(w, of_name) for w in words):
                rank = 0
            elif all(has(w, of_name + spaced(entry.description)) for w in words):
                rank = 1
            else:
                continue
            # The status codes of one command after the tables of them all
            specific = table.kind == "status_values" and table.name not in (
                None,
                "Status Code",
            )
            order = (rank, specific, table.source.document, table.source.figure_nr)
            found.append((order, table, entry))
    if not found:
        return [f"No table of values has '{text}'"]
    # Entries named by the words asked, else those described by them
    best = min(order[0] for order, _, _ in found)
    found = [f for f in found if f[0][0] == best]
    if wanted is None and not words and len(found) > limit:
        return [f"Give a value or a name; {len(found)} entries are of that kind"]

    lines = []
    for _, table, entry in sorted(found, key=lambda f: f[0]):
        head = f"**{entry.value}**" if markdown else entry.value
        title = table_title(table, entry.value_column)
        line = f"{head} {named(entry)}, {title} [{cite(table.source)}]"
        if verbose:
            told = [
                f"{k.replace('_', ' ')}: {v}" for k, v in entry.columns.items() if v
            ]
            if entry.name and entry.description:
                told.insert(0, entry.description.split("\n")[0][:160])
            if told:
                line += ": " + "; ".join(told)
        lines.append(line)
    if len(lines) > limit:
        return lines[:limit] + [f"... and {len(lines) - limit} more"]
    return lines


# What 'status' is asked with: Dword 3 of a completion, a status code type and
# a status code, or a status as a completion holds it, each in hexadecimal
HEX_OF = r"\s*[=:]?\s*(?:0x)?([0-9a-f]+)h?\b"
DWORD_3 = re.compile(rf"\bdw(?:ord)?\s?3{HEX_OF}")
SCT = re.compile(rf"\bsct{HEX_OF}")
SC = re.compile(rf"\bsc{HEX_OF}")
STATUS_ONLY = re.compile(rf"^(?:status(?: field)?)?{HEX_OF}$")
FOR_COMMAND = re.compile(r"\s+(?:of|for)\s+(.+)$")


def status_field(spec: SpecDocument) -> Optional[Structure]:
    """The figure of the Status Field of a completion queue entry"""

    for structure in spec.structures:
        acronyms = {f.acronym for f in structure.fields}
        if "status field" in structure.name.lower() and {"SC", "SCT"} <= acronyms:
            return structure
    return None


def stem(text: str) -> List[str]:
    """The words of 'text' without a plural s, as "Errors" of "error" """

    return [
        w[:-1] if w.endswith("s") else w for w in re.findall(r"[a-z]+", text.lower())
    ]


def of_type(table: Values, named: str) -> bool:
    """Whether 'table' holds status codes of the status code type 'named', as
    the Media and Data Integrity Error status codes of "Media and Data
    Integrity Errors" """

    if not of_kind(table, "status_values") or not table.qualifier:
        return False
    qualifier = stem(table.qualifier)
    return stem(named)[: len(qualifier)] == qualifier


def status(spec: SpecDocument, text: str, verbose=False, markdown=False) -> List[str]:
    """What a status means. 'text' is the status as a completion holds it and
    nvme-cli prints it, "4281h", or Dword 3 of a completion, "dw3 85020000h",
    either split into its fields by the figure of the Status Field; or a
    status code type and a status code, "sct 2h sc 81h". The status code is
    looked up in the tables of its type, and " of Write" keeps those of a
    command where a table is of that command."""

    lower = " ".join(text.lower().split())
    command = None
    match = FOR_COMMAND.search(lower)
    if match:
        command, lower = match[1], lower[: match.start()]
    field = status_field(spec)
    lines: List[str] = []
    sct = re.search(SCT, lower)
    sc = re.search(SC, lower)
    dword = re.search(DWORD_3, lower)
    whole = re.fullmatch(STATUS_ONLY, lower)
    if sct and sc:
        type_of, code = int(sct[1], 16), int(sc[1], 16)
    elif dword or whole:
        given = dword or whole
        assert given is not None
        if field is None:
            return ["No figure of the Status Field in the data model"]
        fields = [
            f for f in field.fields if f.lower is not None and f.upper is not None
        ]
        shift = min(f.lower for f in fields if f.lower is not None)
        held = int(given[1], 16)
        dw3 = held if dword else held << shift
        if dw3 >> 32:
            return [f"Status {held:X}h has more bits than the Status Field"]
        values = {}
        parts = []
        for f in fields:
            assert f.lower is not None and f.upper is not None
            width = f.upper - f.lower + 1
            values[f.acronym] = (dw3 >> f.lower) & ((1 << width) - 1)
            digits = (width + 3) // 4
            shown = (
                f"{values[f.acronym]:0{digits}X}h"
                if width > 1
                else str(values[f.acronym])
            )
            set_flag = width == 1 and values[f.acronym]
            parts.append(f"{f.acronym} {shown}" + (f" ({f.name})" if set_flag else ""))
        status_value = dw3 >> shift
        head = f"Status {status_value:X}h of a completion"
        if dword:
            head = f"DW3 {held:X}h of a completion holds status {status_value:X}h"
        lines.append(f"{head}: {', '.join(parts)} [{cite(field.source)}]")
        type_of, code = values["SCT"], values["SC"]
    else:
        return ["Give a status, as '4281h', or a type and a code, as 'sct 2h sc 81h'"]

    types = [t for t in spec.values if of_kind(t, "status_code_type")]
    named = next(
        ((t, e) for t in types for e in t.entries if within(e.value, type_of)), None
    )
    if named is None:
        lines.append(f"SCT {type_of:X}h, which no table of status code types has")
        return lines
    table, entry = named
    lines.append(f"SCT {type_of:X}h {entry.name or entry.value} [{cite(table.source)}]")

    found = [
        (t, e)
        for t in spec.values
        if of_type(t, entry.name or "")
        for e in t.entries
        if within(e.value, code)
    ]
    # A code of its own is what the code means; a range only points elsewhere
    exact = [(t, e) for t, e in found if "to" not in e.value and "-" not in e.value]
    found = exact or found
    if command:
        of_command = [(t, e) for t, e in found if (t.name or "").lower() == command]
        found = of_command or found
    if not found:
        lines.append(f"SC {code:02X}h, which no table of {entry.name} has")
        return lines
    for t, e in sorted(
        found, key=lambda f: (f[0].source.document, f[0].source.figure_nr)
    ):
        meaning = e.name or e.description.split("\n")[0][:160]
        head = f"**SC {e.value}**" if markdown else f"SC {e.value}"
        line = f"{head} {meaning}, {table_title(t)} [{cite(t.source)}]"
        if verbose and e.name and e.description:
            line += ": " + e.description.split("\n")[0][:160]
        lines.append(line)
    return lines


def section(spec: SpecDocument, key: str) -> List[str]:
    """What the figures of a section describe, the section by its number, with
    its subsections, or by a word of its title"""

    key = key.strip()
    if not key:
        return ["Give the number or title of a section"]
    by_number = re.fullmatch(r"[A-Z]?[\d.]*\d|[A-Z]", key) is not None

    def within(source: Source) -> bool:
        if not source.section:
            return False
        if by_number:
            return source.section == key or source.section.startswith(key + ".")
        return key.lower() in (source.section_title or "").lower()

    found = []
    for command_set in spec.command_sets.values():
        for cmd in command_set.commands.values():
            for d in cmd.sqe:
                found.append((d.source, f"{cmd.name} {dword_label(d, 'cdw')}"))
            for d in cmd.cqe:
                found.append((d.source, f"{cmd.name} {dword_label(d, 'cqe dw')}"))
            for operation in cmd.operations:
                found.append(
                    (operation.source, f"{cmd.name} operation {operation.name}")
                )
    for f in spec.features.values():
        for d in f.sqe:
            found.append((d.source, f"feature {f.name} {dword_label(d, 'cdw')}"))
        for d in f.cqe:
            found.append((d.source, f"feature {f.name} {dword_label(d, 'cqe dw')}"))
    for s in spec.structures:
        found.append((s.source, f"structure {s.name} [{cite(s.source)}]"))
    for v in spec.values:
        kind = "values" if v.kind == "other" else v.kind.replace("_", " ")
        found.append((v.source, f"table of {kind} {v.name or ''} [{cite(v.source)}]"))

    lines = []
    for _, line in sorted(
        (f for f in found if within(f[0])),
        key=lambda f: (f[0].document, f[0].figure_nr),
    ):
        lines.append(line)
    titles = sorted(
        {
            (f[0].document, f[0].section or "", f[0].section_title or "")
            for f in found
            if within(f[0])
        }
    )
    head = [f"{document_name(d)} {n} {t}" for d, n, t in titles[:12]]
    return head + lines if lines else [f"No section '{key}'"]


def section_order(section: Optional[str]) -> List[Tuple[int, int, str]]:
    """A section number as it sorts: "5.2.10" after "5.2.9", and an annex,
    "A.1", after the numbered sections"""

    if not section:
        return []
    return [
        (0, int(part), "") if part.isdigit() else (1, 0, part)
        for part in section.split(".")
    ]


def errata(
    spec: SpecDocument, document: str = "", none: Optional[List[str]] = None
) -> List[str]:
    """The errata of the specification, of the documents whose short name has
    'document' in it, by document and section, each with where it is"""

    found = [
        e
        for e in spec.errata
        if document.lower() in document_name(e.source.document).lower()
    ]
    found.sort(
        key=lambda e: (
            e.source.document,
            section_order(e.source.section),
            e.source.figure_nr,
        )
    )
    # The same value in many rows of a figure is one erratum, said once
    counted: Dict[str, int] = {}
    for e in found:
        line = f"{cite(e.source)}: {e.message}"
        counted[line] = counted.get(line, 0) + 1
    lines = [line + (f" (in {n} rows)" if n > 1 else "") for line, n in counted.items()]
    return lines or (["No errata"] if none is None else none)


def is_example(message: str) -> bool:
    """Whether a figure not modelled is a worked example, by its caption's
    word, and so no data the figure fails to give"""

    return bool(re.search(r"\bexamples?\b", message, re.I))


def lint(spec: SpecDocument, document: str = "") -> List[str]:
    """What reading the figures as data found to look at, of the documents
    whose short name has 'document' in it. First what is the authors': the
    candidate errata and the document errors. Then what senfd could not read
    as data, which is senfd's to learn or the figure's to follow the
    conventions: the figures of no shape it models, the worked examples
    apart, and the dwords no command, feature or operation claims."""

    def of(text: str) -> bool:
        return document.lower() in document_name(text).lower()

    def coded(code: str) -> List[str]:
        return [d.message for d in spec.diagnostics if d.code == code and of(d.message)]

    unmodelled = coded("figure-not-modelled")
    examples = [m for m in unmodelled if is_example(m)]
    unassigned = [
        f"{cite(d.source)}: {dwords_named(name, d)}"
        for name, dwords in sorted(spec.unassigned.items())
        for d in dwords
        if of(d.source.document)
    ]
    sections = [
        ("The authors': candidate errata", errata(spec, document, none=[])),
        ("The authors': document errors", coded("document-error")),
        ("senfd's, or the figure's: rows that name no field", coded("field-name")),
        (
            "senfd's, or the figure's: figures of no shape senfd models",
            [m for m in unmodelled if m not in examples],
        ),
        ("Worked examples, not data", examples),
        ("senfd's, or the caption's: dwords no command claims", unassigned),
    ]
    lines = []
    for title, items in sections:
        lines.append(f"{title} ({len(items)})")
        lines += [f"  {item}" for item in items]
    return lines


# The lookups sate answers on its command line, and the findings senfd lists
LOOKUPS = (
    "command",
    "feature",
    "log-page",
    "structure",
    "section",
    "search",
    "value",
    "status",
)
FINDINGS = ("lint", "errata")

HELP = {
    "command": "A command and its dwords, as 'write' or 'write 12'",
    "feature": "A feature, by hexadecimal identifier or name",
    "log-page": "A log page, by hexadecimal identifier or name",
    "structure": "A data structure or register",
    "section": "What a section describes, by number or title",
    "search": "Fields and things by acronym or name",
    "value": "An entry of a table of values, as 'status code 82h' or 'CNS 05h'",
    "status": "What a status means, as '4281h' or 'sct 2h sc 81h of write'",
    "lint": "What reading the figures as data found, for authors and senfd",
    "errata": "Candidate errata of the documents, with where they are",
}


def run(prog: str, argv: List[str], names: Iterable[str], description: str) -> int:
    """The answer to the lookup or finding of 'names' that 'argv' names, as
    "command write 12", printed; each with the options of the data model"""

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--spec",
        type=Path,
        default=None,
        help=f"The merged data model (default: {default_spec_path()})",
    )
    common.add_argument(
        "-v", "--verbose", action="store_true", help="Give the descriptions too"
    )
    common.add_argument(
        "--markdown",
        action="store_true",
        help="Give the fields of an answer as Markdown tables, for reading",
    )
    parser = argparse.ArgumentParser(prog=prog, description=description)
    sub = parser.add_subparsers(dest="what", required=True)
    for name in names:
        p = sub.add_parser(name, parents=[common], help=HELP[name])
        if name in FINDINGS:
            p.add_argument("document", nargs="?", default="")
        else:
            p.add_argument("words", nargs="+")
    args = parser.parse_args(argv)

    try:
        spec = load(args.spec)
    except OSError as exc:
        print(
            f"{prog}: no data model to answer from: {exc}. Make one from "
            "the documents with: senfd <documents>.docx --output ~/.cache/senfd",
            file=sys.stderr,
        )
        return 1
    text = " ".join(getattr(args, "words", []))
    if args.what == "command":
        words, dword = args.words, None
        if len(words) > 1 and words[-1].isdigit():  # "write 12", of cdw12
            words, dword = words[:-1], int(words[-1])
        lines = command(spec, " ".join(words), dword, args.verbose, args.markdown)
    elif args.what == "feature":
        lines = feature(spec, text, args.verbose, args.markdown)
    elif args.what == "log-page":
        lines = log_page(spec, text, args.verbose, args.markdown)
    elif args.what == "structure":
        lines = structure(spec, text, args.verbose, args.markdown)
    elif args.what == "section":
        lines = section(spec, text)
    elif args.what == "errata":
        lines = errata(spec, args.document)
    elif args.what == "lint":
        lines = lint(spec, args.document)
    elif args.what == "value":
        lines = value(spec, text, args.verbose, args.markdown)
    elif args.what == "status":
        lines = status(spec, text, args.verbose, args.markdown)
    else:
        lines = search(spec, text)
    print("\n".join(linked(spec, lines) if args.markdown else lines))
    return 0
