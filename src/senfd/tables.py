import re
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field

import senfd.errors
from senfd.errors import Error


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

    ncells: int = Field(default_factory=int)
    headers: List[str] = Field(default_factory=list)
    values: List[List[str]] = Field(default_factory=list)

    @classmethod
    def from_enriched_figure(cls, figure) -> Tuple[Optional["Grid"], List[Error]]:
        if figure.table is None:
            return None, [
                senfd.errors.FigureTableMissingError(
                    figure_nr=figure.figure_nr, message="No table"
                )
            ]
        if len(figure.table.rows) < 2:
            return None, [
                senfd.errors.FigureTableMissingRowsError(
                    figure_nr=figure.figure_nr, message=r"Number of rows < 2"
                )
            ]
        if not hasattr(figure, "REGEX_GRID"):
            return None, [
                senfd.errors.FigureRegexGridMissingError(
                    figure_nr=figure.figure_nr, message="Missing REGEX_GRID"
                )
            ]

        errors = []
        lengths = list(set([len(row.cells) for row in figure.table.rows]))
        if len(lengths) != 1:
            errors.append(
                senfd.errors.IrregularTableError(
                    figure_nr=figure.figure_nr,
                    message=f"Varying row lengths({lengths})",
                    lengths=lengths,
                )
            )

        data = figure.table.dict()
        data["ncells"] = max(lengths)

        regex_hdr, regex_val = zip(*figure.REGEX_GRID)

        header_names: List[str] = []
        values = []
        for idx, row in enumerate(figure.table.rows):
            if not header_names:
                header_matches = [
                    match.group(1)
                    for match in (
                        re.match(regex, cell.text.strip().replace("\n", " "))
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

        if not grid_table.headers:
            errors.append(
                senfd.errors.FigureNoGridHeaders(
                    figure_nr=figure.figure_nr,
                    message=(
                        "Grid is missing headers;"
                        f" check {figure.__class__.__name__}.REGEX_GRID"
                    ),
                )
            )
        if not grid_table.values:
            errors.append(
                senfd.errors.FigureNoGridValues(
                    figure_nr=figure.figure_nr,
                    message=(
                        "Grid is missing values;"
                        f" check {figure.__class__.__name__}.REGEX_GRID"
                    ),
                )
            )

        return grid_table, errors
