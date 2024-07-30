from pathlib import Path

from senfd.documents.categorized import FromFigureDocument
from senfd.documents.figure import FromDocx
from senfd.errors import TableError

CONVERTERS = [FromDocx, FromFigureDocument]


def process(input: Path, output: Path) -> List[TableError]:
    all_errors = []

    for converter in CONVERTERS:
        if not converter.is_applicable(input):
            continue

        document, errors = converter.convert(input)
        all_errors += errors

        document.to_html_file(output)
        json_path = document.to_json_file(output)
        all_errors += process(json_path, output)
        break

    return all_errors
