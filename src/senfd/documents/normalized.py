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
    left_open,
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


class Placement(BaseModel):
    """The range of a field under a condition heading the ranges, as "HDGSTF=1";
    None where the column says the field is not present"""

    condition: str
    range: Optional[Range] = None


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
    # The cases of the field: the tables in its description whose first
    # column is headed by another field of the layout
    cases: List["LayoutCase"] = Field(default_factory=list)
    # The range of the field under each condition heading the columns of
    # ranges, where they differ, as "HDGSTF=1" and "HDGSTF=0"
    placements: List[Placement] = Field(default_factory=list)


class LayoutCase(BaseModel):
    """
    The meaning of a field while another field of its layout has one of the
    listed values. For example, bits 15:08 of Zone Management Receive are the
    Reporting Options when the Zone Receive Action is Report Zones or
    Extended Report Zones. A case holds the name, acronym and description of
    the field in that case, and the layouts and values of its tables.
    """

    # The header that names the controlling field, for example "Zone Receive Action"
    selector: str
    # The values of the controlling field that the case applies to, by name
    when: List[str] = Field(default_factory=list)
    # Whether the case applies to every value that no other case lists, as
    # the row "All other values" says
    otherwise: bool = False
    name: Optional[str] = None
    acronym: Optional[str] = None
    description: str = ""
    layouts: List["Layout"] = Field(default_factory=list)
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
    # The paragraphs of its section before it that refer to it by number
    mentions: List[str] = Field(default_factory=list)
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
    sections: Dict[str, str] = Field(default_factory=dict)
    """The title of each numbered section, by its number as printed"""


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


def note_left_open(text: str, what: str, diagnostics: List[Diagnostic]) -> None:
    """A note in 'diagnostics' where 'text' is a name and an acronym whose
    parenthesis the document leaves open; 'what' says which row has it, as
    "Field 02"; the spec document takes the note as a candidate erratum"""

    opened = left_open(text)
    if opened:
        name, acronym = opened
        said = f"the parenthesis of its acronym '{acronym}' is not closed"
        diagnostics.append(note("acronym-open", f"{what} {name}: {said}"))


REGEX_NOT_PRESENT = re.compile(r"^not present$", flags=re.IGNORECASE)


def under_conditions(
    row: Row, grid: List[str], unit: str, conditions: int
) -> Optional[Values]:
    """The values of a row whose first column, of the ranges, the PDF gives a
    cell for each of 'conditions', the header one: the cells of the ranges
    and then one for each other column; None of another row"""

    others = [c for i, c in enumerate(grid) if not i or c != grid[i - 1]]
    if (
        not others
        or others[0] != unit
        or len(row.cells) != conditions + len(others) - 1
    ):
        return None
    ranges, rest = row.cells[:conditions], row.cells[conditions:]
    values = Values(spans=len(row.cells))
    values.texts[unit] = ranges[0].text.strip()
    values.cells[unit] = list(ranges)
    for column, cell in zip(others[1:], rest):
        values.texts[column] = cell.text.strip()
        values.cells[column] = [cell]
    return values


def placed(unit: str, conditions: List[str], texts: List[str]) -> List[Placement]:
    """The range of a field under each of the 'conditions' heading the columns
    of ranges, from the texts of its cells there; none where there are no
    conditions or the ranges are the same under each"""

    texts = [normalize_text(t) for t in texts]
    if not conditions or len(texts) != len(conditions) or len(set(texts)) == 1:
        return []
    return [
        Placement(
            condition=condition,
            range=None if REGEX_NOT_PRESENT.match(text) else parse_range(unit, text),
        )
        for condition, text in zip(conditions, texts)
    ]


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
    active: List[str] = []
    held: List[Tuple[LayoutField, List[Table]]] = []
    for row in rows:
        leading = [normalize_text(c.text) for c in row.cells]
        leading = leading[
            : next(
                (i for i, t in enumerate(leading) if not REGEX_CONDITION.match(t)),
                len(leading),
            )
        ]
        if len(leading) > 1:
            # Conditions heading the columns of ranges below them, which the
            # PDF may give in more cells than the header has columns
            diagnostics.append(
                note("range-condition", f"Ranges by condition: {leading}")
            )
            active = leading
            continue
        values = values_of(row, grid)
        if values is None and len(active) > 1:
            values = under_conditions(row, grid, unit, len(active))
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
            active = conditions
            continue

        # A row of one cell spanning the table is its notes, or heads the rows
        # below it. So does a row with a single text, unless one of its cells
        # holds a table, for example an unnamed byte with a table of its bits
        tabled = any(c.tables for cells in values.cells.values() for c in cells)
        if values.spans == 1 or (len(set(filled)) == 1 and not tabled):
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
        placements = placed(unit, active, [c.text for c in range_cells])
        if len(active) > 1 and len(range_cells) == len(active):
            detail = ""  # The cells are the ranges under the conditions
        if placements:
            present = [p.range for p in placements if p.range is not None]
            range_text = present[0].text if present else range_text

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
        note_left_open(
            values.texts.get(text_column, ""), f"Field {rng.text}", diagnostics
        )
        if text_column == "name" and "description" in values.texts:
            description = values.texts["description"]
        if name is None and description:
            diagnostics.append(
                note("field-name", f"Field without a name: '{description[:60]}'")
            )

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
                placements=placements,
            )
        )
        tables = [t for cells in values.cells.values() for c in cells for t in c.tables]
        held.append((layout.fields[-1], tables))
        elided = False

    # Read the tables in the cells only after every field of the layout is
    # known, because a table of cases is recognised by the other field that
    # heads its first column
    for field, tables in held:
        siblings = [other for other in layout.fields if other is not field]
        for table in tables:
            cases = parse_cases(table, siblings, diagnostics)
            if cases:
                field.cases += cases
            else:
                read_nested(table, field, diagnostics)
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
    note_left_open(
        values.texts.get(text_column, ""),
        f"Field {texts.get('bits') or normalize_text(byte_text)}",
        diagnostics,
    )
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


def read_nested(table: Table, into, diagnostics: List[Diagnostic]) -> None:
    """Add 'table', from a cell of the field or case 'into', to 'into': as a
    layout where the table has the header of a layout, and otherwise as
    values"""

    layout = parse_nested(table, diagnostics)
    if layout:
        into.layouts.append(layout)
    else:
        into.values += parse_nested_values(table, diagnostics)


REGEX_OTHERWISE = re.compile(r"^all other(?:s| values)?$", flags=re.IGNORECASE)


def parse_cases(
    table: Table, others: List[LayoutField], diagnostics: List[Diagnostic]
) -> List[LayoutCase]:
    """
    The cases in 'table', a table in the cell of a field. A table of cases has
    two columns, and its first column is headed by the name of one of
    'others', the other fields of the layout, for example "Zone Receive
    Action". Each row gives the meaning of the field while that other field
    has the value that the row names. A row whose second cell is merged with
    the cell above adds a value to the case above it. The row "All other
    values" is the case for every value that no row names. The result is
    empty when 'table' is not a table of cases.
    """

    idx, headers, grid, _ = find_header(table.rows)
    columns = unique(grid)
    names = {slug(n) for other in others for n in (other.name, other.acronym) if n}
    if (
        idx is None
        or len(columns) != 2
        or slug(normalize_text(headers[0])) not in names
    ):
        return []

    cases: List[LayoutCase] = []
    for row in table.rows[idx + 1 :]:
        values = values_of(row, grid)
        if values is None or values.spans != 2:
            diagnostics.append(
                warning("row-length", f"Row of {len(row.cells)} cells, header of 2")
            )
            continue
        named = normalize_text(values.texts.get(columns[0], ""))
        cells = values.cells.get(columns[1], [])
        if cases and cells and all(cell.merged == "up" for cell in cells):
            cases[-1].when += [named] if named else []
            continue
        name, acronym, description = parse_field_description(
            values.texts.get(columns[1], "")
        )
        otherwise = bool(REGEX_OTHERWISE.match(named))
        case = LayoutCase(
            selector=normalize_text(headers[0]),
            when=[] if otherwise or not named else [named],
            otherwise=otherwise,
            name=name,
            acronym=acronym,
            description=description,
        )
        for cell in cells:
            for nested in cell.tables:
                read_nested(nested, case, diagnostics)
        cases.append(case)
    return cases


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
            note_left_open(values.texts["description"], "Entry", diagnostics)
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
            note_left_open(values.texts["name"], "Entry", diagnostics)
            if name and acronym and REGEX_ENTRY_ACRONYM.match(acronym):
                entry["name"], entry["acronym"] = name, acronym
        if section:
            entry["section"] = section
        entries.append(entry)
    return entries


BITS_OF_A_BYTE = [str(bit) for bit in range(7, -1, -1)]


def parse_byte_diagram(rows: List[Row]) -> Optional[Layout]:
    """
    The layout of a diagram with one row for each byte and the bits as
    columns, as the protection information formats are drawn: a row with the
    bits 7 to 0 under "Bit", then one row for each byte, numbered from 0. A
    field spans the bytes from the row marked "MSB" to the row marked "LSB",
    and its name is the one other text in those rows. The columns "msb_byte"
    and "lsb_byte" of a field are the bytes that hold its most and its least
    significant bits. None when the rows are not such a diagram, or when a
    byte belongs to no field.
    """

    texts = [
        [t for t in (normalize_text(c.text) for c in row.cells if not c.merged) if t]
        for row in rows
    ]
    if (
        BITS_OF_A_BYTE not in texts
        or ["Bit"] not in texts[: texts.index(BITS_OF_A_BYTE)]
    ):
        return None

    layout = Layout(unit="bytes")
    first: Optional[int] = None
    names: List[str] = []
    for byte, row in enumerate(texts[texts.index(BITS_OF_A_BYTE) + 1 :]):
        told = row[1:] if row[:1] == ["Byte"] else row
        if told[:1] != [str(byte)]:
            return None
        if "MSB" in told:
            if first is not None:
                return None
            first = byte
        if first is None:
            return None
        names += [t for t in told[1:] if t not in ("MSB", "LSB")]
        if "LSB" in told:
            rng = parse_range("bytes", f"{byte}:{first}")
            if len(names) != 1 or rng is None:
                return None
            layout.fields.append(
                LayoutField(
                    range=rng,
                    name=names[0],
                    columns={"msb_byte": str(first), "lsb_byte": str(byte)},
                )
            )
            first, names = None, []
    return layout if layout.fields and first is None else None


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
        mentions=figure.mentions,
        subject=parse_caption(caption),
    )

    rows = figure.table.rows[1:]  # The first row is the caption
    diagram = parse_byte_diagram(rows)
    if diagram:
        normalized.headers, normalized.columns = ["Byte", "Bit"], ["bytes", "bits"]
        normalized.shape, normalized.layout = "layout", diagram
        diagnostics.append(note("byte-diagram", "Diagram of bytes by their bits"))
        return normalized
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

    column = record_column(grid, body) if shape is None else None
    if column:
        normalized.shape = "layout"
        filled = [r for r in body if any(normalize_text(c.text) for c in r.cells)]
        layout = parse_layout(filled, grid, diagnostics, headers)
        normalized.layout = records_of(layout, column)
        diagnostics.append(note("records", f"Records numbered by '{column}'"))
    elif shape == "layout":
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


# A record of a table of records, as "Range 0" of the ranges of Dataset Management
REGEX_RECORD = re.compile(r"^(?P<name>[A-Za-z][A-Za-z ]*?) (?P<index>\d+)$")


def record_column(grid: List[str], body: List[Row]) -> Optional[str]:
    """
    The first column of 'grid' where it numbers the records of a table of
    their fields by bytes, as "Range 0" and "Range 1" of NVM 1.3 Figure 47,
    and otherwise None
    """

    if not grid or "bytes" not in grid or not {"name", "description"} & set(grid):
        return None
    column = grid[0]
    if column in ("bytes", "bits", "name", "description"):
        return None
    names, numbers = set(), set()
    for row in body:
        text = normalize_text(row.cells[0].text) if row.cells else ""
        if not text or REGEX_ELISION.match(text):
            continue
        match = REGEX_RECORD.match(text)
        if not match:
            return None
        names.add(match["name"])
        numbers.add(int(match["index"]))
    return column if len(names) == 1 and len(numbers) > 1 else None


def records_of(layout: Layout, column: str) -> Layout:
    """
    'layout' as a field for each record that 'column' numbers, its range the
    bytes of the record's fields, and its layout those fields with their bytes
    counted from the start of the record; 'layout' as it is where a field has
    a range that is no number
    """

    def text(upper: int, lower: int) -> str:
        return f"{upper:02d}:{lower:02d}" if upper != lower else f"{lower:02d}"

    groups: List[Tuple[str, List[LayoutField]]] = []
    for field in layout.fields:
        if field.range.upper is None or field.range.lower is None:
            return layout
        name = field.columns.get(column, "")
        if not groups or groups[-1][0] != name:
            groups.append((name, []))
        groups[-1][1].append(field)

    records = Layout(unit=layout.unit, notes=layout.notes)
    for name, fields in groups:
        upper = max(f.range.upper or 0 for f in fields)
        lower = min(f.range.lower or 0 for f in fields)
        inner = [
            f.model_copy(
                update={
                    "range": Range(
                        unit=f.range.unit,
                        text=text(
                            (f.range.upper or 0) - lower, (f.range.lower or 0) - lower
                        ),
                        upper=(f.range.upper or 0) - lower,
                        lower=(f.range.lower or 0) - lower,
                    ),
                    "columns": {k: v for k, v in f.columns.items() if k != column},
                    "elided": False,
                }
            )
            for f in fields
        ]
        records.fields.append(
            LayoutField(
                range=Range(
                    unit=layout.unit, text=text(upper, lower), upper=upper, lower=lower
                ),
                name=name,
                section=fields[0].section,
                elided=fields[0].elided,
                layouts=[Layout(unit=layout.unit, fields=inner)],
            )
        )
    return records


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
        document.sections = figure_document.sections

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
