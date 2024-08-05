from typing import List

from pydantic import BaseModel


class Error(BaseModel):
    message: str


class TableOfFiguresError(Error):
    tof_entry_nr: int
    caption: str


class TableError(Error):
    table_nr: int
    caption: str


class FigureError(Error):
    figure_nr: int


class FigureTableMissingError(FigureError):
    pass


class FigureTableMissingRowsError(FigureError):
    pass


class FigureRegexGridMissingError(FigureError):
    pass


class FigureNoGridHeaders(FigureError):
    pass


class FigureNoGridValues(FigureError):
    pass


class TableOfFiguresDescriptionMismatchError(FigureError):
    tof_entry_nr: int
    caption_tof_entry: str
    caption_table_row: str


class FigureDuplicateNumberError(FigureError):
    caption_existing: str
    caption_toinsert: str


class IrregularTableError(FigureError):
    lengths: List[int]
