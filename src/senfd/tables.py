from typing import List

from pydantic import BaseModel, Field


class Cell(BaseModel):
    text: str = Field(default_factory=str)
    tables: List["Table"] = Field(default_factory=list)


class Row(BaseModel):
    cells: List[Cell] = Field(default_factory=list)


class Table(BaseModel):
    """
    Tabular data in the most raw form, can be irregular, that is, varying amount of
    cells in each row.
    """

    table_nr: int = Field(default_factory=int)
    rows: List[Row] = Field(default_factory=list)


class Grid(BaseModel):
    """
    Grids are regular, that is, each row has the same amount of cells and cells are
    named. Also, their content match
    """

    headers: List[str] = Field(default_factory=list)
    fields: List[str] = Field(default_factory=list)
    values: List[List[str | int | None]] = Field(default_factory=list)
