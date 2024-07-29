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
    rows: List[Row] = Field(default_factory=list)


class HeaderTable(Table):
    """
    Header tables are regular, that is, each row has the same amount of cells and cells
    are named. What the actual content is needs further processing.
    """

    ncells: int = Field(default_factory=int)
    headers: List[str] = Field(default_factory=list)
