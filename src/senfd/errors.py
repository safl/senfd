from typing import Any, List

from pydantic import BaseModel


class Error(BaseModel):
    message: str


class TableOfFiguresError(Error):
    caption: str


class TableCaptionError(Error):
    caption: str


class TableHeaderError(Error):
    caption: str
    cells: List[Any]


class IrregularTableError(Error):
    lengths: List[int]


class NonTableHeaderError(Error):
    pass


class FigureError(Error):
    pass
