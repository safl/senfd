from pathlib import Path

from senfd.documents.categorized import FromFigureDocument
from senfd.documents.figure import FromDocx

CONVERTERS = [FromDocx, FromFigureDocument]


def process(input: Path, output: Path):
    all_errors = []

    next_stage = []
    for converter in CONVERTERS:
        if not converter.is_applicable(input):
            continue

        document, errors = converter.convert(input)
        next_stage.append(document.to_json_file(output))

        all_errors += errors

    for path in next_stage:
        all_errors += process(path, output)

    return all_errors
