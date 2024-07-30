import json
from collections import namedtuple
from pathlib import Path
from typing import Any, Dict, List

from pydantic import BaseModel

from senfd.documents.base import to_file

TableOfFiguresError = namedtuple("TableOfFiguresError", ["message", "caption"])

TableCaptionError = namedtuple("TableCaptionError", ["message", "caption"])

TableHeaderError = namedtuple("TableHeaderError", ["message", "caption", "cells"])

IrregularTableError = namedtuple("IrregularTableError", ["message", "lengths"])

NonTableHeaderError = namedtuple("NonTableHeaderError", ["message"])

TableError = (
    TableOfFiguresError
    | TableCaptionError
    | TableHeaderError
    | IrregularTableError
    | NonTableHeaderError
)


def error_to_dict(error: TableError) -> Dict[str, List[Any]]:
    error_dict = error._asdict()
    for key, value in error_dict.items():
        if isinstance(value, BaseModel):
            error_dict[key] = value.dict()
    return error_dict


def to_log_file(errors: List[TableError], filename: str, output: Path) -> Path:

    content = json.dumps(
        [{"type": type(error).__name__, **error_to_dict(error)} for error in errors],
        indent=4,
    )

    return to_file(content, f"{filename}.error.log", output)
