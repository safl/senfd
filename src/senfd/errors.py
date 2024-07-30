from collections import namedtuple
from typing import Any, Dict, List

from pydantic import BaseModel

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
