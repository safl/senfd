"""
Answers to questions about the specification, from its merged model

Each answer is a few lines of text, saying the figure of the document it came
from, so that it can be checked against the specification. The model is the
merged specification document that senfd writes, by default in the cache:

    senfd *.docx --output ~/.cache/senfd
    senfd-query command write 12
"""

import argparse
import os
import re
from pathlib import Path
from typing import Iterable, List, Optional

from senfd.documents.spec import (
    Bits,
    Command,
    Dwords,
    Source,
    SpecDocument,
    Structure,
    alias,
)


def default_spec_path() -> Path:
    if os.environ.get("SENFD_SPEC"):
        return Path(os.environ["SENFD_SPEC"])
    cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return cache / "senfd" / "merged.spec.document.json"


def load(path: Optional[Path] = None) -> SpecDocument:
    path = path or default_spec_path()
    return SpecDocument.model_validate_json(path.read_text(encoding="utf-8"))


def cite(source: Source) -> str:
    """The document and figure of 'source', the document by a short name, as
    "Base 2.2, Figure 12" """

    match = re.match(
        r"NVM Express (?P<name>.+?) Specification,? Revision (?P<revision>[\d\-.]+)",
        source.document,
    )
    name = (
        re.sub(r" Command Set$", "", match["name"])
        + " "
        + match["revision"].replace("-", ".")
        if match
        else source.document
    )
    return f"{name}, Figure {source.figure_nr}"


def bits(field: Bits) -> str:
    rng = field.range  # As the document writes it
    acronym = f" ({field.acronym})" if field.acronym else ""
    return f"{rng} {field.name or ''}{acronym}"


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
        if field.fields:
            yield from lines_of_fields(field.fields, verbose, indent + "    ")


def dword_label(dwords: Dwords, prefix: str) -> str:
    span = (
        f"{prefix}{dwords.lower}"
        if dwords.lower == dwords.upper
        else f"{prefix}{dwords.lower}-{dwords.upper}"
    )
    condition = f" if {dwords.condition}" if dwords.condition else ""
    return f"{span}{condition} [{cite(dwords.source)}]"


def lines_of_dwords(
    dwords: List[Dwords], prefix: str, dword: Optional[int], verbose: bool
) -> Iterable[str]:
    for d in sorted(dwords, key=lambda d: (d.lower, d.condition or "")):
        if dword is not None and not d.lower <= dword <= d.upper:
            continue
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
    spec: SpecDocument, name: str, dword: Optional[int] = None, verbose=False
) -> List[str]:
    lines = []
    found = [
        (command_set, key)
        for command_set in spec.command_sets.values()
        for key in find(command_set.commands, name)
    ]
    # A command of the name given rather than those whose names contain it
    exact = [(cs, key) for cs, key in found if key == alias(name)]
    for command_set, key in exact or found:
        cmd: Command = command_set.commands[key]
        lines.append(
            f"{cmd.name}: {command_set.name} command, opcode {cmd.opcode:02X}h "
            f"[{cite(cmd.source)}]"
        )
        lines += lines_of_dwords(cmd.sqe, "cdw", dword, verbose)
        if dword is None:
            lines += lines_of_dwords(cmd.cqe, "cqe dw", None, verbose)
        for operation in cmd.operations:
            selectors = " ".join(
                f"{k}={v:02X}h" for k, v in operation.selectors.items()
            )
            lines.append(
                f"operation {operation.name}, {selectors} [{cite(operation.source)}]"
            )
            lines += lines_of_dwords(operation.sqe, "cdw", dword, verbose)
            if dword is None:
                lines += lines_of_dwords(operation.cqe, "cqe dw", None, verbose)
                lines += [f"  returns {name}" for name in operation.structures]
    return lines or [f"No command '{name}'"]


def by_identifier_or_name(items: dict, key: str) -> list:
    match = re.fullmatch(r"(?:0x)?([0-9A-Fa-f]{1,2})h?", key.strip())
    if match:
        identifier = int(match[1], 16)
        found = [item for item in items.values() if item.identifier == identifier]
        if found:
            return found
    return [items[k] for k in find(items, key)]


def feature(spec: SpecDocument, key: str, verbose=False) -> List[str]:
    lines = []
    for f in by_identifier_or_name(spec.features, key):
        lines.append(f"{f.identifier:02X}h {f.name} [{cite(f.source)}]")
        lines += lines_of_dwords(f.sqe, "cdw", None, verbose)
        lines += lines_of_dwords(f.cqe, "cqe dw", None, verbose)
    return lines or [f"No feature '{key}'"]


def log_page(spec: SpecDocument, key: str, verbose=False) -> List[str]:
    lines = []
    for page in by_identifier_or_name(spec.log_pages, key):
        lines.append(f"{page.identifier:02X}h {page.name} [{cite(page.source)}]")
        if page.structure:
            lines += lines_of_structure(page.structure, verbose)
    return lines or [f"No log page '{key}'"]


def lines_of_structure(structure: Structure, verbose: bool) -> List[str]:
    offset = f" at offset {structure.offset}" if structure.offset else ""
    lines = [f"{structure.name}{offset}, {structure.unit} [{cite(structure.source)}]"]
    lines += lines_of_fields(structure.fields, verbose)
    lines += [f"  Note: {note[:160]}" for note in structure.notes if verbose]
    return lines


def structure(spec: SpecDocument, name: str, verbose=False) -> List[str]:
    key = alias(name)
    named = [s for s in spec.structures if alias(s.name) == key] or [
        s for s in spec.structures if key in alias(s.name)
    ]
    if len(named) > 8:
        return [f"{len(named)} structures; be more specific:"] + [
            f"  {s.name} [{cite(s.source)}]" for s in named[:40]
        ]
    lines = []
    for s in named:
        lines += lines_of_structure(s, verbose)
    return lines or [f"No structure '{name}'"]


def search(spec: SpecDocument, text: str, limit: int = 40) -> List[str]:
    """Fields by acronym or name, and things by name, with where they are"""

    needle = text.strip().lower()
    hits: List[str] = []

    def match(field: Bits) -> bool:
        return (field.acronym or "").lower() == needle or needle in (
            field.name or ""
        ).lower()

    def fields(where: str, items: List[Bits]):
        for field in items:
            if match(field):
                hits.append(f"{where}: {bits(field).strip()}")
            fields(where, field.fields)

    for command_set in spec.command_sets.values():
        for cmd in command_set.commands.values():
            if needle in cmd.name.lower():
                hits.append(f"command {cmd.name} [{cite(cmd.source)}]")
            for d in cmd.sqe:
                fields(f"{cmd.name} {dword_label(d, 'cdw')}", d.fields)
            for d in cmd.cqe:
                fields(f"{cmd.name} {dword_label(d, 'cqe dw')}", d.fields)
    for f in spec.features.values():
        if needle in f.name.lower():
            hits.append(f"feature {f.identifier:02X}h {f.name} [{cite(f.source)}]")
        for d in f.sqe + f.cqe:
            fields(f"feature {f.name} {dword_label(d, 'dw')}", d.fields)
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


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Answer questions about the specification from its model"
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
    sub = parser.add_subparsers(dest="what", required=True)
    p = sub.add_parser("command", help="A command and its dwords")
    p.add_argument("name")
    p.add_argument("dword", nargs="?", type=int)
    sub.add_parser("feature", help="A feature, by identifier or name").add_argument(
        "key"
    )
    sub.add_parser("log-page", help="A log page, by identifier or name").add_argument(
        "key"
    )
    sub.add_parser("structure", help="A data structure or register").add_argument(
        "name"
    )
    sub.add_parser("search", help="Fields and things by acronym or name").add_argument(
        "text"
    )
    args = parser.parse_args(argv)

    spec = load(args.spec)
    if args.what == "command":
        lines = command(spec, args.name, args.dword, args.verbose)
    elif args.what == "feature":
        lines = feature(spec, args.key, args.verbose)
    elif args.what == "log-page":
        lines = log_page(spec, args.key, args.verbose)
    elif args.what == "structure":
        lines = structure(spec, args.name, args.verbose)
    else:
        lines = search(spec, args.text)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
