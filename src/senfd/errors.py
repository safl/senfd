import json
from collections import namedtuple
from pathlib import Path
from typing import List, NamedTuple

from senfd.documents.base import to_file

TableCaptionError = namedtuple("TableCaptionError", ["table_nr", "caption", "message"])

TableOfFiguresError = namedtuple("TableOfFiguresError", ["caption", "message"])


def to_log_file(errors: List[NamedTuple], filename: str, output: Path) -> Path:

    content = json.dumps(
        [{"type": type(error).__name__, **error._asdict()} for error in errors],
        indent=4,
    )

    return to_file(content, f"{filename}.error.log", output)
