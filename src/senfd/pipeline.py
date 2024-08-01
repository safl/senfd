from pathlib import Path
from typing import List, Type

from senfd.documents.base import Converter
from senfd.documents.enriched import FromFigureDocument
from senfd.documents.plain import FromDocx
from senfd.errors import TableError

CONVERTERS: List[Type[Converter]] = [FromDocx, FromFigureDocument]


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
