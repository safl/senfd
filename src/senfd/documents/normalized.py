# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
The normalised figure document: each tabular figure by the shape of its table
and the subject of its caption

A table's shape is decided by its header, whose columns are matched by name
rather than by position. Layout tables, the bits or bytes of fields, are parsed
into fields; tables of values, opcodes and transitions into entries naming
their columns; any other table is kept as its rows of cells, by header. What
was normalised, and what could not be, is in the diagnostics.
"""

import re
from argparse import Namespace
from pathlib import Path
from typing import ClassVar, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from senfd.documents.base import Converter, Document, strip_all_suffixes
from senfd.documents.plain import FigureDocument
from senfd.errors import Error
from senfd.normalize import (
    REGEX_ENTRY_ACRONYM,
    slug,
    Diagnostic,
    Range,
    Subject,
    normalize_caption,
    normalize_header,
    normalize_text,
    note,
    parse_caption,
    parse_field_description,
    parse_range,
    shape_of,
    warning,
)
from senfd.ranges import Unit
from senfd.skiplist import SkipPatterns
from senfd.tables import Cell, Row, Table


class LayoutField(BaseModel):
    """
    A field of a layout table: its range, name, acronym and description, the
    other columns of its row by their name, the heading it is under, and the
    layouts of the tables in its description
    """

    range: Range
    name: Optional[str] = None
    acronym: Optional[str] = None
    description: str = ""
    columns: Dict[str, str] = Field(default_factory=dict)
    section: Optional[str] = None
    # Whether rows are left out before it, as "..." between the first and the
    # last of entries counted by a value
    elided: bool = False
    layouts: List["Layout"] = Field(default_factory=list)
    # The tables of values in its description, as the values a field selecting
    # an operation takes, by the names of their columns
    values: List[Dict[str, str]] = Field(default_factory=list)


class Layout(BaseModel):
    unit: Unit
    fields: List[LayoutField] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class NormalizedFigure(BaseModel):
    figure_nr: int
    caption: str
    page_nr: Optional[int] = None
    pdf_page: Optional[int] = None
    section: Optional[str] = None
    section_title: Optional[str] = None
    subject: Subject
    shape: Optional[str] = None
    headers: List[str] = Field(default_factory=list)
    columns: List[str] = Field(default_factory=list)
    layout: Optional[Layout] = None
    entries: List[Dict[str, str]] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    rows: List[List[str]] = Field(default_factory=list)


class NormalizedFigureDocument(Document):
    SUFFIX_JSON: ClassVar[str] = ".normalized.figure.document.json"
    SUFFIX_HTML: ClassVar[str] = ".normalized.figure.document.html"

    FILENAME_SCHEMA: ClassVar[str] = "normalized.figure.document.schema.json"
    FILENAME_HTML_TEMPLATE: ClassVar[str] = "normalized.figure.document.html.jinja2"

    figures: List[NormalizedFigure] = Field(default_factory=list)
    # The figures a skip list leaves out, by number, with why
    skipped: Dict[int, str] = Field(default_factory=dict)
    nontabular: List[int] = Field(default_factory=list)
    diagnostics: List[Diagnostic] = Field(default_factory=list)


def header_of(row: Row) -> Tuple[List[str], List[str]]:
    """
    The text and the column of each grid position of the header 'row'; a
    header cell merged across positions names each of them
    """

    headers: List[str] = []
    columns: List[str] = []
    for idx, cell in enumerate(row.cells):
        if cell.merged == "left" and idx:
            headers.append(headers[-1])
            columns.append(columns[-1])
            continue
        header = normalize_text(cell.text)
        headers.append(header)
        columns.append(normalize_header(header)[0] or f"column{idx}")

    # Headers that differ by a number only, as "Command 1" and "Command 2", are
    # columns of their own rather than one header with footnote markers
    for idx, column in enumerate(columns):
        same = [
            i
            for i, c in enumerate(columns)
            if c == column and headers[i] != headers[idx]
        ]
        if same:
            for i in [idx, *same]:
                columns[i] = slug(headers[i]) or columns[i]
    return headers, columns


REGEX_NOTES = re.compile(r"^notes?\b", flags=re.IGNORECASE)
REGEX_ELISION = re.compile(r"^(?:\.\.\.|\u2026)$")
# A condition heading columns of ranges, as "HDGSTF=1" over the bytes a field
# is when the header digest is present, and "HDGSTF=0" over those when not
REGEX_CONDITION = re.compile(r"^[A-Z][A-Z0-9_]*\s*=\s*\w+$")


def is_header_again(texts: List[str], headers: List[str]) -> bool:
    """Whether a row of 'texts' is the header of 'headers' again, as the
    documents repeat it after a page break"""

    return [t.lower() for t in texts] == [h.lower() for h in headers]


def find_header(
    rows: List[Row],
) -> Tuple[Optional[int], List[str], List[str], Optional[str]]:
    """
    The index of the header row among 'rows', the text and the column of each
    of its grid positions, and the shape the columns make; the header is the
    first of the first rows making a shape, else the first row
    """

    for idx, row in enumerate(rows[:3]):
        headers, columns = header_of(row)
        shape = shape_of(columns)
        if shape:
            return idx, headers, columns, shape
    if not rows:
        return None, [], [], None
    headers, columns = header_of(rows[0])
    return 0, headers, columns, None


def unique(items: List[str]) -> List[str]:
    return list(dict.fromkeys(items))


class Values(BaseModel):
    """The text and the cells of each column of a row"""

    texts: Dict[str, str] = Field(default_factory=dict)
    cells: Dict[str, List[Cell]] = Field(default_factory=dict)
    spans: int = 0


def values_of(row: Row, grid: List[str]) -> Optional[Values]:
    """
    The values of 'row' by the columns of the header's grid positions 'grid',
    or None when the row has another number of positions

    A cell merged across the positions of more than one column belongs to the
    description or name among them, else to the first; a column whose header
    is merged across positions joins the text of its cells.
    """

    if len(row.cells) != len(grid):
        # The row spans other grid columns than the header, as Word allows; its
        # cells are taken one to one with the header's, or as a heading
        spans = [cell for cell in row.cells if cell.merged != "left"]
        columns = [c for i, c in enumerate(grid) if not i or c != grid[i - 1]]
        if len(spans) == 1:
            return Values(texts={grid[0]: spans[0].text.strip()}, spans=1)
        if len(spans) != len(columns):
            return None
        return Values(
            texts={c: cell.text.strip() for c, cell in zip(columns, spans)},
            cells={c: [cell] for c, cell in zip(columns, spans)},
            spans=len(spans),
        )
    values = Values()
    idx = 0
    while idx < len(row.cells):
        end = idx + 1
        while end < len(row.cells) and row.cells[end].merged == "left":
            end += 1
        covered = unique(grid[idx:end])
        target = next((c for c in ("description", "name") if c in covered), covered[0])
        cell = row.cells[idx]
        text = cell.text.strip()
        if target in values.texts and text:
            values.texts[target] = f"{values.texts[target]} {text}".strip()
        else:
            values.texts.setdefault(target, text)
        values.cells.setdefault(target, []).append(cell)
        values.spans += 1
        idx = end
    return values


def parse_layout(
    rows: List[Row],
    grid: List[str],
    diagnostics: List[Diagnostic],
    headers: Optional[List[str]] = None,
) -> Layout:
    # A header of both bytes and bits gives each byte range the bits in it, a
    # row each, the range of the bytes merged down over the rows of its bits
    nests_bits = "bytes" in grid and "bits" in grid
    unit: Unit = "bytes" if nests_bits or "bits" not in grid else "bits"
    text_column = "name" if "name" in grid else "description"
    columns = unique(grid)
    others = [c for c in columns if c not in ("bytes", "bits", "name", "description")]

    layout = Layout(unit=unit)
    section = None
    elided = False
    for row in rows:
        values = values_of(row, grid)
        if values is None:
            row_texts = [normalize_text(cell.text) for cell in row.cells]
            diagnostics.append(
                warning(
                    "row-length",
                    f"Row of {len(row.cells)} cells, header of {len(grid)}: {row_texts}",
                )
            )
            continue

        texts = {c: normalize_text(t) for c, t in values.texts.items()}
        if (
            headers
            and is_header_again([normalize_text(c.text) for c in row.cells], headers)
        ) or texts.get(unit, "").lower() in ("bit", "bits", "byte", "bytes"):
            continue  # The header again, as after a page break

        filled = [t for t in texts.values() if t]
        if filled and all(REGEX_ELISION.match(t) for t in filled):
            elided = True  # Entries left out, as between the first and the last
            continue
        if REGEX_ELISION.match(texts.get(unit, "")) and REGEX_ELISION.match(
            texts.get(text_column, "")
        ):
            elided = True  # The same, with something in another column
            continue

        # Conditions heading the ranges below them are neither a field nor a
        # heading of its fields
        conditions = [normalize_text(c.text) for c in values.cells.get(unit, [])]
        if conditions and all(REGEX_CONDITION.match(c) for c in conditions):
            diagnostics.append(
                note("range-condition", f"Ranges by condition: {conditions}")
            )
            continue

        # A row of one cell spanning the table is its notes, or heads the rows
        # below it; so does a row of one text
        if values.spans == 1 or len(set(filled)) == 1:
            text = filled[0] if filled else None
            if text and REGEX_NOTES.match(text):
                layout.notes.append(text)
            else:
                section = text
            continue

        if nests_bits:
            if nest_bits(layout, values, text_column, section, diagnostics):
                section = None  # It named the byte range, and heads no more
            continue

        if all(cell.merged == "up" for cell in values.cells.get(unit, [])):
            # The range of the row above, going on; its description continues,
            # unless that is merged with the row above too
            text_cells = values.cells.get(text_column, [])
            more = values.texts.get(text_column, "")
            if layout.fields and more and not all(c.merged == "up" for c in text_cells):
                field = layout.fields[-1]
                field.description = "\n".join(p for p in [field.description, more] if p)
            continue

        # A header spanning two cells of a row, the range and a detail of it;
        # a range of "NOTE 1" is one a note gives, and the row a field
        range_cells = values.cells.get(unit, [])
        range_text = range_cells[0].text if range_cells else values.texts.get(unit, "")
        detail = " ".join(normalize_text(c.text) for c in range_cells[1:]).strip()

        rng = parse_range(unit, range_text)
        if rng is None:
            diagnostics.append(
                warning("range", f"Row without a range: {list(texts.values())}")
            )
            continue
        if rng.lower is None:
            diagnostics.append(
                note("range-symbolic", f"Range not a number: '{rng.text}'")
            )

        name, acronym, description = parse_field_description(
            values.texts.get(text_column, "")
        )
        if text_column == "name" and "description" in values.texts:
            description = values.texts["description"]
        if name is None and description:
            diagnostics.append(
                note("field-name", f"Field without a name: '{description[:60]}'")
            )

        nested: List[Layout] = []
        enumerated: List[Dict[str, str]] = []
        for cells in values.cells.values():
            for cell in cells:
                for table in cell.tables:
                    nested_layout = parse_nested(table, diagnostics)
                    if nested_layout:
                        nested.append(nested_layout)
                    else:
                        enumerated += parse_nested_values(table, diagnostics)

        layout.fields.append(
            LayoutField(
                range=rng,
                name=name,
                acronym=acronym,
                description=description,
                columns={c: texts.get(c, "") for c in others}
                | ({f"{unit}_detail": detail} if detail else {}),
                section=section,
                elided=elided,
                layouts=nested,
                values=enumerated,
            )
        )
        elided = False
    return layout


def nest_bits(
    layout: Layout,
    values: Values,
    text_column: str,
    section: Optional[str],
    diagnostics: List[Diagnostic],
) -> bool:
    """The bits of a row of a layout of bytes and bits, into the byte range of
    the row above where the range is merged with it, else into a byte range of
    its own, named by the heading above it, which names the range rather than
    heading it, and True where it did; a row of no bits, "n/a", is a byte
    range alone, named by its own text"""

    texts = {c: normalize_text(t) for c, t in values.texts.items()}
    name, acronym, description = parse_field_description(
        values.texts.get(text_column, "")
    )
    byte_cells = values.cells.get("bytes", [])
    byte_text = byte_cells[0].text if byte_cells else values.texts.get("bytes", "")
    if texts.get("bits", "").lower() in ("", "n/a"):
        rng = parse_range("bytes", byte_text)
        if rng is None:
            diagnostics.append(
                warning("range", f"Row without a range: {list(texts.values())}")
            )
            return False
        layout.fields.append(
            LayoutField(
                range=rng,
                name=name,
                acronym=acronym,
                description=description,
                section=section,
            )
        )
        return False

    bits = parse_range("bits", values.texts.get("bits", ""))
    if bits is None:
        diagnostics.append(
            warning("range", f"Row without a range: {list(texts.values())}")
        )
        return False
    field = LayoutField(
        range=bits,
        name=name,
        acronym=acronym,
        description=description,
    )

    above = layout.fields[-1] if layout.fields else None
    if (
        above
        and above.layouts
        and byte_cells
        and all(c.merged == "up" for c in byte_cells)
    ):
        above.layouts[0].fields.append(field)
        return False
    rng = parse_range("bytes", byte_text)
    if rng is None:
        diagnostics.append(
            warning("range", f"Row without a range: {list(texts.values())}")
        )
        return False
    layout.fields.append(
        LayoutField(
            range=rng,
            name=section,
            layouts=[Layout(unit="bits", fields=[field])],
        )
    )
    return section is not None


def parse_nested(table: Table, diagnostics: List[Diagnostic]) -> Optional[Layout]:
    """The layout of a table in a cell, which has a header and no caption"""

    idx, headers, grid, shape = find_header(table.rows)
    if shape != "layout" or idx is None:
        return None
    return parse_layout(table.rows[idx + 1 :], grid, diagnostics, headers)


def parse_nested_values(
    table: Table, diagnostics: List[Diagnostic]
) -> List[Dict[str, str]]:
    """The entries of a table of values in a cell, as the values of a field,
    the value in the column "value", whatever its header, as "PIT Value" """

    idx, headers, grid, shape = find_header(table.rows)
    if idx is None or not (shape or is_named_header(headers)):
        return []
    # The value column is decided once for the table: the one named "value",
    # else one named for a value, else the first, as "Select" of a table of
    # the values of the field Select
    if "value" not in grid:
        named = [c for c in grid if c.endswith("_value")]
        first = named[0] if named else grid[0]
        grid = ["value" if c == first else c for c in grid]
    grid = [
        "description"
        if column.endswith(("_definition", "_description"))
        and "description" not in grid
        else column
        for column in grid
    ]
    return parse_entries(table.rows[idx + 1 :], grid, diagnostics, headers, [])


def parse_entries(
    rows: List[Row],
    grid: List[str],
    diagnostics: List[Diagnostic],
    headers: List[str],
    notes: List[str],
) -> List[Dict[str, str]]:
    """
    The entries of a table of values, opcodes, requirements or transitions; a
    row of one cell is a note, into 'notes', or heads the entries below it, as
    their "section"
    """

    entries = []
    section = None
    for row in rows:
        values = values_of(row, grid)
        if values is None:
            diagnostics.append(
                warning(
                    "row-length",
                    f"Row of {len(row.cells)} cells, header of {len(grid)}",
                )
            )
            continue
        if is_header_again([normalize_text(c.text) for c in row.cells], headers):
            continue
        entry = {c: normalize_text(t) for c, t in values.texts.items()}
        filled = [t for t in entry.values() if t]
        if not filled or all(REGEX_ELISION.match(t) for t in filled):
            continue
        if values.spans == 1:
            if REGEX_NOTES.match(filled[0]):
                notes.append(filled[0])
            else:
                section = filled[0]
            continue
        if entry.get("description") and "name" not in entry:
            name, acronym, rest = parse_field_description(values.texts["description"])
            if name:
                entry["name"] = name
                if acronym and REGEX_ENTRY_ACRONYM.match(acronym):
                    entry["acronym"] = acronym
                elif acronym:
                    # Words saying something of the name, which keeps them
                    entry["name"] = f"{name} ({acronym})"
                entry["description"] = normalize_text(rest)
        elif entry.get("name") and "acronym" not in entry:
            name, acronym, _ = parse_field_description(values.texts["name"])
            if name and acronym and REGEX_ENTRY_ACRONYM.match(acronym):
                entry["name"], entry["acronym"] = name, acronym
        if section:
            entry["section"] = section
        entries.append(entry)
    return entries


def normalize_figure(figure, diagnostics: List[Diagnostic]) -> NormalizedFigure:
    caption, caption_diagnostics = normalize_caption(figure.description)
    diagnostics += caption_diagnostics
    normalized = NormalizedFigure(
        figure_nr=figure.figure_nr,
        caption=caption,
        page_nr=figure.page_nr,
        pdf_page=figure.pdf_page,
        section=figure.section,
        section_title=figure.section_title,
        subject=parse_caption(caption),
    )

    rows = figure.table.rows[1:]  # The first row is the caption
    idx, headers, grid, shape = find_header(rows)
    normalized.headers, normalized.columns, normalized.shape = (
        unique(headers),
        unique(grid),
        shape,
    )
    if idx is None:
        return normalized
    if idx:
        diagnostics.append(note("header-row", f"Header in row {idx + 2}"))
    body = rows[idx + 1 :]

    # The header goes on in the rows below it while a cell of it is merged down
    # into them; a header cell spanning columns names them by the cells below
    while (
        body
        and len(body[0].cells) == len(grid)
        and any(c.merged == "up" for c in body[0].cells)
    ):
        below = body.pop(0)
        # Which header cells span columns, before any column is renamed
        spanning = [grid.count(column) > 1 for column in grid]
        for i, cell in enumerate(below.cells):
            if cell.merged is None and spanning[i] and normalize_text(cell.text):
                text = normalize_text(cell.text)
                grid[i] = normalize_header(text)[0] or grid[i]
                headers[i] = f"{headers[i]} {text}"
        diagnostics.append(note("header-rows", "Header of more than one row"))
    normalized.headers, normalized.columns = unique(headers), unique(grid)
    shape = shape_of(grid) or shape
    normalized.shape = shape

    if shape == "layout":
        normalized.layout = parse_layout(body, grid, diagnostics, headers)
    elif shape:
        normalized.entries = parse_entries(
            body, grid, diagnostics, headers, normalized.notes
        )
    elif is_named_header(headers):
        # A table of no shape senfd knows, as the steps of a flow or the fields
        # of version descriptors, is entries by the names of its columns
        normalized.shape = "table"
        normalized.entries = parse_entries(
            body, grid, diagnostics, headers, normalized.notes
        )
    else:
        normalized.rows = [
            [normalize_text(c.text) for c in row.cells if c.merged != "left"]
            for row in body
        ]
    return normalized


def is_named_header(headers: List[str]) -> bool:
    """Whether 'headers' name columns, rather than number them as a diagram of
    bits does, or leave them empty"""

    named = {h for h in headers if re.search(r"[A-Za-z]{2}", h)}
    return len(named) >= 2 and len(named) * 2 >= len(set(headers))


class FromFigureDocument(Converter):
    @staticmethod
    def is_applicable(path: Path) -> bool:
        return "".join(path.suffixes).lower() == FigureDocument.SUFFIX_JSON

    @staticmethod
    def convert(path: Path, args: Namespace) -> Tuple[Document, List[Error]]:
        figure_document = FigureDocument.model_validate_json(
            path.read_text(encoding="utf-8")
        )
        document = NormalizedFigureDocument()
        document.meta.stem = strip_all_suffixes(path.stem)
        document.meta.file = figure_document.meta.file
        document.meta.sha256 = figure_document.meta.sha256

        skip_patterns = SkipPatterns(
            getattr(args, "skip_figures", None), figure_document.figures
        )
        for figure in figure_document.figures:
            if not figure.table:
                document.nontabular.append(figure.figure_nr)
                continue
            skip = skip_patterns.skip_figure(figure)
            if skip:
                document.skipped[figure.figure_nr] = skip.description
                continue

            diagnostics: List[Diagnostic] = []
            document.figures.append(normalize_figure(figure, diagnostics))
            for diagnostic in diagnostics:
                diagnostic.figure_nr = figure.figure_nr
            document.diagnostics += diagnostics

        return document, []
