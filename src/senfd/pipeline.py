from pathlib import Path

from senfd.documents.categorized import FromFigureDocument
from senfd.documents.figure import FromDocx

CONVERTERS = [FromDocx, FromFigureDocument]


def process(input: Path, output: Path):
    all_errors = []

    for converter in CONVERTERS:
        if not converter.is_applicable(input):
            continue

        document, errors = converter.convert(input)
        all_errors += errors

        all_errors += process(document.to_json_file(output), output)
        break

    return all_errors
