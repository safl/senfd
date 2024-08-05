from typing import List

from pydantic import BaseModel


class Error(BaseModel):
    message: str


class TableCaptionError(Error):
    caption: str


class TableOfFiguresError(Error):
    caption: str


class FigureError(Error):
    figure_nr: int


class FigureTableMissingError(FigureError):
    pass


class FigureTableMissingRowsError(FigureError):
    pass


class FigureRegexGridMissingError(FigureError):
    pass


class TableOfFiguresDescriptionMismatchError(FigureError):
    caption_tof_entry: str
    caption_table_row: str


class FigureDuplicateNumberError(FigureError):
    caption_existing: str
    caption_toinsert: str


class IrregularTableError(FigureError):
    lengths: List[int]
