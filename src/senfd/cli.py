# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
Command-Line Interface
======================

Produces normalised figure documents and a model of the specification, as
``.json``, from the ``.docx`` documents of the specification.
"""

import json
import sys
from argparse import ArgumentParser, Namespace, RawTextHelpFormatter
from pathlib import Path
from typing import List, Optional, Tuple

import senfd
import senfd.pipeline
import senfd.query
import senfd.schemas
from senfd.documents import get_document_classes
from senfd.documents.base import to_file
from senfd.documents.plain import FigureDocument
from senfd.documents.spec import SpecDocument, document_name, merge
from senfd.errors import Error
from senfd.normalize import Diagnostic

PARSEARGS_EPILOG = """\
Senfd
=====

The --skip-figures flag specifies a path to a TOML file containing a list of
figures to be skipped during processing.

The TOML file must follow this format:

[[skip]]
regex = "^Decimal.and.Binary.Units$"
matches = 1
description = ""

[[skip]]
regex = "^Byte, Word, and Dword Relationships$"
matches = 1
description = ""


Each entry under [[skip]] consists of:
  - regex: A regular expression matching the figure description.
  - matches: The expected number of occurrences of this figure in the document.
  - description: An optional text field describing the reason for skipping.

This allows flexible and pattern-based skipping of figures during execution.
"""


def to_log_file(errors: List[Error], filename: str, output: Path) -> Path:
    content = json.dumps(
        [{"type": type(error).__name__, **error.model_dump()} for error in errors],
        indent=4,
    )

    return to_file(content, f"{filename}.error.log", output)


def parse_args() -> Namespace:
    """Return command-line arguments"""

    parser = ArgumentParser(
        description=(
            "Make the data model of NVMe specification documents, .docx, and say "
            "what reading them found; senfd-query lint lists it"
        ),
        epilog=PARSEARGS_EPILOG,
        formatter_class=RawTextHelpFormatter,
    )
    parser.add_argument(
        "document", nargs="*", type=Path, help="path to one or more document(s)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="directory where the output will be saved",
        default=Path("output"),
    )
    parser.add_argument(
        "--dump-schema",
        action="store_true",
        help="dump schema(s) and exit",
    )
    parser.add_argument(
        "--skip-figures",
        type=Path,
        help="Path to toml file that contains list of figure classifiers to skip",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="print the version and exit",
    )
    args = parser.parse_args()
    if not args.document and not args.dump_schema and not args.version:
        parser.error("the following arguments are required: document")

    return args


def main() -> int:
    """Command-line entrypoint"""

    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    if args.version:
        print(senfd.__version__)
        return 0

    if args.dump_schema:
        for docclass in get_document_classes():
            print(docclass.to_schema_file(args.output))
        return 0

    missing = [str(path) for path in args.document if not path.is_file()]
    if missing:
        print(f"senfd: no such document: {', '.join(missing)}", file=sys.stderr)
        return 1

    found: List[Diagnostic] = []
    for path in sorted(args.document):
        args.output.mkdir(parents=True, exist_ok=True)

        errors = senfd.pipeline.process(path, args.output, args)
        # Named as every other output of the document is, "2-4" of "2.4"
        stem = path.stem.replace(".", "-")
        to_log_file(errors, stem, args.output)
        found += document_errors(errors, stem, args.output)

    specs = [
        SpecDocument.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(args.output.glob(f"*{SpecDocument.SUFFIX_JSON}"))
        if not path.name.startswith("merged.")
    ]
    if specs:
        spec = merge(specs)
        spec.diagnostics += found
        written = spec.to_json_file(args.output / spec.json_filename())
        print(summary(spec, len(args.document), written))

    return 0


def document_errors(errors: List[Error], stem: str, output: Path) -> List[Diagnostic]:
    """The errors of reading the document of 'stem', each said with the document
    and where in it, by the figure a table follows, as diagnostics of the data
    model"""

    name = document_name(stem)
    plain = output / f"{stem}{FigureDocument.SUFFIX_JSON}"
    after: List[Tuple[int, int, Optional[int]]] = []
    if plain.exists():
        figures = FigureDocument.model_validate_json(plain.read_text(encoding="utf-8"))
        after = sorted(
            (f.table.table_nr, f.figure_nr, f.page_nr)
            for f in figures.figures
            if f.table is not None
        )

    def where(error: Error) -> str:
        figure_nr = getattr(error, "figure_nr", None)
        table_nr = getattr(error, "table_nr", None)
        entry_nr = getattr(error, "tof_entry_nr", None)
        if figure_nr is not None:
            return f"Figure {figure_nr}"
        if table_nr is not None:
            before = [a for a in after if a[0] < table_nr]
            if not before:
                return "a table before the first figure"
            _, nr, page = before[-1]
            return f"the table after Figure {nr}" + (f", page {page}" if page else "")
        if entry_nr is not None:
            return f"entry {entry_nr} of the table of figures"
        return ""

    found = []
    for error in errors:
        at = where(error)
        # A cell quoted by its first line, as a caption is one
        caption = (getattr(error, "caption", "") or "").strip().split("\n")[0]
        caption = caption if len(caption) <= 80 else caption[:77].rstrip() + "..."
        said = error.message + (f": '{caption}'" if caption else "")
        found.append(
            Diagnostic(
                severity="warning",
                code="document-error",
                message=f"{name}, {at}: {said}" if at else f"{name}: {said}",
            )
        )
    return found


def plural(n: int, one: str, many: str = "") -> str:
    return f"{n} {one if n == 1 else many or one + 's'}"


def summary(spec: SpecDocument, documents: int, written: Path) -> str:
    """What a run made of the documents, and what of them to look at, with the
    command listing it for the data model just written"""

    def counted(code: str) -> int:
        return sum(d.code == code for d in spec.diagnostics)

    commands = sum(len(s.commands) for s in spec.command_sets.values())
    errata = senfd.query.errata(spec, none=[])
    unassigned = sum(len(d) for d in spec.unassigned.values())
    default = written.resolve() == senfd.query.default_spec_path().resolve()
    spec_option = "" if default else f" --spec {written}"
    return (
        f"{documents} document{'s' if documents != 1 else ''} into {written}: "
        f"{commands} commands, {len(spec.features)} features, "
        f"{len(spec.log_pages)} log pages and {len(spec.structures)} structures.\n"
        f"For the authors: {plural(len(errata), 'candidate erratum', 'candidate errata')}"
        f" and {plural(counted('document-error'), 'document error')}. "
        f"For senfd, or the figures: "
        f"{plural(counted('figure-not-modelled'), 'figure')} not modelled and "
        f"{plural(unassigned, 'unassigned dwords', 'unassigned dwords')}.\n"
        f"List them: senfd-query{spec_option} lint"
    )


if __name__ == "__main__":
    main()
