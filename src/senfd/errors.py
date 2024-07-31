from typing import Any, List

from pydantic import BaseModel


class TableError(BaseModel):
    message: str


class TableOfFiguresError(TableError):
    caption: str


class TableCaptionError(TableError):
    caption: str


class TableHeaderError(TableError):
    caption: str
    cells: List[Any]


class IrregularTableError(TableError):
    lengths: List[int]


class NonTableHeaderError(TableError):
    pass
