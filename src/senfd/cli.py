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
from argparse import ArgumentParser, Namespace, RawTextHelpFormatter
from pathlib import Path
from typing import List

import senfd
import senfd.pipeline
import senfd.query
import senfd.schemas
from senfd.documents import get_document_classes
from senfd.documents.base import to_file
from senfd.documents.spec import SpecDocument, merge
from senfd.errors import Error

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
        description="Semantically organize and enrich figures",
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
            docclass.to_schema_file(args.output)
        return 0

    errors_of_documents = 0
    for path in sorted(args.document):
        args.output.mkdir(parents=True, exist_ok=True)

        errors = senfd.pipeline.process(path, args.output, args)
        # Named as every other output of the document is, "2-4" of "2.4"
        to_log_file(errors, path.stem.replace(".", "-"), args.output)
        errors_of_documents += len(errors)

    specs = [
        SpecDocument.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(args.output.glob(f"*{SpecDocument.SUFFIX_JSON}"))
        if not path.name.startswith("merged.")
    ]
    if specs:
        spec = merge(specs)
        written = spec.to_json_file(args.output / spec.json_filename())
        print(summary(spec, len(args.document), errors_of_documents, written))

    return 0


def summary(spec: SpecDocument, documents: int, errors: int, written: Path) -> str:
    """What a run made of the documents, and what of them to look at"""

    commands = sum(len(s.commands) for s in spec.command_sets.values())
    errata = [line for line in senfd.query.errata(spec) if line != "No errata"]
    unmodelled = sum(d.code == "figure-not-modelled" for d in spec.diagnostics)
    unassigned = sum(len(d) for d in spec.unassigned.values())
    return (
        f"{documents} document{'s' if documents != 1 else ''} into {written}: "
        f"{commands} commands, {len(spec.features)} features, "
        f"{len(spec.log_pages)} log pages and {len(spec.structures)} structures. "
        f"To look at: {len(errata)} candidate errata (senfd-query errata), "
        f"{unmodelled} figure{'s' if unmodelled != 1 else ''} not modelled and "
        f"{unassigned} unassigned dwords "
        f"(senfd-query lint), and {errors} document errors (*.error.log)."
    )


if __name__ == "__main__":
    main()
