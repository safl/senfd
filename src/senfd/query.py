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
    senfd-query command write 12
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
    Source,
    SpecDocument,
    Structure,
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
            yield indent + "  " + field.description.split("\n")[0][:160]
        if verbose:
            for value in field.values:
                # The name, else the start of the description, for reading
                name = (senfd_value_names(value) or [value.description[:60]])[0]
                yield f"{indent}    = {value.value} {name}".rstrip()
        if field.fields:
            yield from lines_of_fields(field.fields, verbose, indent + "    ")


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
                text = (field.description or "").split("\n")[0][:160]
                values = [
                    f"{v.value} {(senfd_value_names(v) or [v.description[:60]])[0]}"
                    for v in field.values
                ]
                if values:
                    text += " Values: " + ", ".join(values)
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
    named = [s for s in spec.structures if alias(s.name) == key] + [
        s for s in spec.structures if key in alias(s.name) and alias(s.name) != key
    ]
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
    for source, line in sorted(
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
    examples = [m for m in unmodelled if re.search(r"\bexamples?\b", m, re.I)]
    unassigned = [
        f"{cite(d.source)}: {dwords_named(name, d)}"
        for name, dwords in sorted(spec.unassigned.items())
        for d in dwords
        if of(d.source.document)
    ]
    sections = [
        ("The authors': candidate errata", errata(spec, document, none=[])),
        ("The authors': document errors", coded("document-error")),
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


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Answer questions about the specification from its data model"
    )
    parser.add_argument(
        "--spec",
        type=Path,
        default=None,
        help=f"The merged specification document (default: {default_spec_path()})",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Give the descriptions too"
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Give the fields of an answer as Markdown tables, for reading",
    )
    sub = parser.add_subparsers(dest="what", required=True)
    p = sub.add_parser("command", help="A command and its dwords")
    p.add_argument("name")
    p.add_argument("dword", nargs="?", type=int)
    sub.add_parser(
        "feature", help="A feature, by hexadecimal identifier or name"
    ).add_argument("key")
    sub.add_parser(
        "log-page", help="A log page, by hexadecimal identifier or name"
    ).add_argument("key")
    sub.add_parser("structure", help="A data structure or register").add_argument(
        "name"
    )
    sub.add_parser(
        "section", help="What a section describes, by number or title"
    ).add_argument("key")
    sub.add_parser(
        "errata", help="Candidate errata of the documents, with where they are"
    ).add_argument("document", nargs="?", default="")
    sub.add_parser(
        "lint", help="What reading the figures as data found, for authors and senfd"
    ).add_argument("document", nargs="?", default="")
    sub.add_parser("search", help="Fields and things by acronym or name").add_argument(
        "text"
    )
    args = parser.parse_args(argv)

    try:
        spec = load(args.spec)
    except OSError as exc:
        print(
            f"senfd-query: no data model to answer from: {exc}. Make one from "
            "the documents with: senfd <documents>.docx --output ~/.cache/senfd",
            file=sys.stderr,
        )
        return 1
    if args.what == "command":
        lines = command(spec, args.name, args.dword, args.verbose, args.markdown)
    elif args.what == "feature":
        lines = feature(spec, args.key, args.verbose, args.markdown)
    elif args.what == "log-page":
        lines = log_page(spec, args.key, args.verbose, args.markdown)
    elif args.what == "structure":
        lines = structure(spec, args.name, args.verbose, args.markdown)
    elif args.what == "section":
        lines = section(spec, args.key)
    elif args.what == "errata":
        lines = errata(spec, args.document)
    elif args.what == "lint":
        lines = lint(spec, args.document)
    else:
        lines = search(spec, args.text)
    print("\n".join(linked(spec, lines) if args.markdown else lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
