import re
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field

import senfd.errors


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


class Grid(BaseModel):
    """
    Grids are regular, that is, each row has the same amount of cells and cells are
    named. Also, their content match
    """

    ncells: int = Field(default_factory=int)
    headers: List[str] = Field(default_factory=list)
    values: List[List[str]] = Field(default_factory=list)

    @classmethod
    def from_enriched_figure(
        cls, figure
    ) -> Tuple[Optional["Grid"], Optional[senfd.errors.TableError]]:
        if figure.table is None:
            return None, senfd.errors.NonTableHeaderError(message="No table")
        if len(figure.table.rows) < 2:
            return None, senfd.errors.NonTableHeaderError(
                message="Insufficent number of rows"
            )
        lengths = list(set([len(row.cells) for row in figure.table.rows]))
        if len(lengths) != 1:
            return None, senfd.errors.IrregularTableError(
                message=f"Varying row lengths({lengths})", lengths=lengths
            )

        if not hasattr(figure, "REGEX_GRID"):
            return None, senfd.errors.FigureError(message="Has not REGEX_GRID")

        data = figure.table.dict()
        data["ncells"] = lengths[0]

        regex_hdr, regex_val = zip(*figure.REGEX_GRID)

        header_names: List[str] = []
        values = []
        for idx, row in enumerate(figure.table.rows):
            if not header_names:
                header_matches = [
                    match.group(1)
                    for match in (
                        re.match(regex, cell.text.strip())
                        for cell, regex in zip(row.cells, regex_hdr)
                    )
                    if match
                ]
                if len(header_matches) == len(regex_hdr):
                    header_names = header_matches
                continue

            value_matches = [
                match.group(1)
                for match in (
                    re.match(regex, cell.text.strip())
                    for cell, regex in zip(row.cells, regex_val)
                )
                if match
            ]
            if len(value_matches) == len(regex_val):
                values.append(value_matches)

        data["headers"] = header_names
        data["values"] = values

        grid_table = cls(**data)

        return grid_table, None
