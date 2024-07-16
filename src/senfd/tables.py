from typing import List

from pydantic import BaseModel, Field


class Cell(BaseModel):
    text: str = Field(default_factory=str)
    tables: List["Table"] = Field(default_factory=list)


class Row(BaseModel):
    cells: List[Cell] = Field(default_factory=list)


class Table(BaseModel):
    rows: List[Row] = Field(default_factory=list)
