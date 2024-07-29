"""
Command-Line Interface
======================

Produces organized and semantically enriched ``.json`` documents from
"""

from argparse import ArgumentParser, Namespace
from pathlib import Path

import senfd
import senfd.errors
import senfd.pipeline
import senfd.schemas
from senfd.documents import get_document_classes


def parse_args() -> Namespace:
    """Return command-line arguments"""

    parser = ArgumentParser(description="Semantically organize and enrich figures")
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

    for path in args.document:
        errors = senfd.pipeline.process(path, args.output)
        senfd.errors.to_log_file(errors, path.stem, args.output)

    return 0
