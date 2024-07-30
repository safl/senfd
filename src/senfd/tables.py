from typing import ClassVar, List, NamedTuple, Optional, Tuple

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


class HeaderTable(Table):
    """
    Header tables are regular, that is, each row has the same amount of cells and cells
    are named. What the actual content is needs further processing.
    """

    VALID_NAMES: ClassVar[List[str]] = [
        "Bits",
        "Bytes",
        "Description",
        "Definition",
        "Value",
    ]

    ncells: int = Field(default_factory=int)
    headers: List[str] = Field(default_factory=list)

    @classmethod
    def from_table(cls, table: Table) -> Tuple[Optional[Table], Optional[NamedTuple]]:

        lengths = list(set([len(row.cells) for row in table.rows]))
        if len(lengths) != 1:
            return None, senfd.errors.IrregularTableError(
                f"Varying row lengths({lengths})", lengths
            )

        if len(table.rows) < 2:
            return None, senfd.errors.NonTableHeaderError("Insufficent number of rows")

        headers = [
            cell.text.strip()
            for cell in table.rows[1].cells
            if cell.text.strip() in cls.VALID_NAMES
        ]
        if len(headers) != len(table.rows[1].cells):
            return None, senfd.errors.TableHeaderError(
                "Unsupported names",
                table.rows[0].cells[0].text,
                [cell.text for cell in table.rows[1].cells],
            )

        data = table.dict()
        data["ncells"] = lengths[0]
        data["headers"] = headers

        enriched = cls(**data)

        return enriched, None
