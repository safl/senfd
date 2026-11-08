# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
A table of a tagged PDF as senfd's rows of cells, as a table of a .docx is

The structure tree gives each row its cells but not the columns a cell
spans: a merged cell is one cell fewer in its row, or an empty one below. The
borders drawn on the page give the columns, so each cell is placed by the
borders beside its text, and an empty cell with no border above it continues
the cell above it.
"""

from collections import defaultdict
from typing import Dict, List, NamedTuple, Optional, Sequence, Set, Tuple

from pdfplumber.utils import extract_text as text_of_chars

from senfd.pdf.pages import LINE, Box, Pages, Vertical, grid, spans, union
from senfd.pdf.tree import TaggedCell, paragraphs, rows
from senfd.tables import Cell, Row, Table


# How far, in points, a table's border may lie outside its text: the
# padding of a cell, with room to spare, but less than the margin a change
# bar is drawn in
PADDING = 12


class Read(NamedTuple):
    """A cell as read from the tree: its text, the box it is printed in on
    each page, the page it starts on, and the tables nested in it"""

    text: str
    boxes: Dict[int, Box]
    page: Optional[int]
    tables: List[Table]


class Placed(NamedTuple):
    """Where a row is printed, and the columns each of its cells spans"""

    page: Optional[int]
    top: Optional[float]
    spans: List[Tuple[int, int]]


def table_of(
    pages: Pages, tagged: Sequence[Sequence[TaggedCell]]
) -> Tuple[List[Row], Dict[int, List[Box]]]:
    """The rows of the table whose cells the tree gives as 'tagged', and the
    boxes of its text on each page it is on"""

    used: Dict[int, Set[int]] = defaultdict(set)
    nested: Dict[int, List[Box]] = defaultdict(list)
    read_rows = [
        [read_cell(pages, cell, used, nested) for cell in row] for row in tagged
    ]
    by_page: Dict[int, List[Box]] = defaultdict(list)
    for read_row in read_rows:
        for read in read_row:
            for number, box in read.boxes.items():
                by_page[number].append(box)
    columns = {
        number: columns_of(pages, number, boxes, nested.get(number, []))
        for number, boxes in by_page.items()
    }
    out, placed = placed_rows(pages, read_rows, columns)
    orphans(
        pages,
        out,
        placed,
        {n: c.edges for n, c in columns.items()},
        {n: c.extent for n, c in columns.items()},
        used,
    )
    return out, by_page


def read_cell(
    pages: Pages,
    cell: TaggedCell,
    used: Dict[int, Set[int]],
    nested: Dict[int, List[Box]],
) -> Read:
    """A cell's text and where it is printed, with the tables nested in it;
    the marked content read is added to 'used', and the extent of each nested
    table to 'nested', whose borders are not the cell's table's"""

    inner_tables: list = []
    found = paragraphs(cell.element, cell.page, inner_tables)
    for paragraph in found:
        for leaf in paragraph:
            used[pages.number(leaf.page)].add(leaf.mcid)
    text, boxes = pages.text(found)
    tables = []
    for element, page in inner_tables:
        for paragraph in paragraphs(element, page):
            for leaf in paragraph:
                used[pages.number(leaf.page)].add(leaf.mcid)
        inner, inner_boxes = table_of(pages, rows(element, page))
        tables.append(Table(rows=inner))
        for number, printed in inner_boxes.items():
            extent: Optional[Box] = None
            for box in printed:
                extent = union(extent, box)
            if extent:
                x0, top, x1, bottom = extent
                nested[number].append((x0 - 3, top - 3, x1 + 3, bottom + 3))
    start: Optional[int] = next(iter(boxes), None)
    if start is None and cell.page is not None:
        start = pages.number(cell.page)
    return Read(text, boxes, start, tables)


class Columns(NamedTuple):
    """The columns of a table on a page: their edges, the borders giving them,
    and the extent of the table's text"""

    edges: List[float]
    verticals: List[Vertical]
    extent: Box


def columns_of(
    pages: Pages, number: int, boxes: Sequence[Box], nested: Sequence[Box]
) -> Columns:
    """The columns of the table on page 'number', by the borders beside its
    text: not those of a table nested in a cell, nor a line in the margin
    beside the table, as a change bar"""

    extent: Optional[Box] = None
    for box in boxes:
        extent = union(extent, box)
    assert extent is not None
    verticals = [
        v
        for v in pages.verticals(number, extent)
        if extent[0] - PADDING <= v[0] <= extent[2] + PADDING
        and not any(
            n[0] < v[0] < n[2]
            and min(v[2], n[3]) - max(v[1], n[1]) > 0.5 * (v[2] - v[1])
            for n in nested
        )
    ]
    return Columns(grid(verticals), verticals, extent)


def placed_rows(
    pages: Pages, read_rows: Sequence[Sequence[Read]], columns: Dict[int, Columns]
) -> Tuple[List[Row], List[Placed]]:
    """The rows of cells, each cell in the columns its borders give it, a
    merged cell repeated in each column it spans; and where each row is"""

    width = max((len(c.edges) - 1 for c in columns.values()), default=0)
    out: List[Row] = []
    placed: List[Placed] = []
    above: List[Cell] = []
    bottom_above: Dict[int, float] = {}
    for read_row in read_rows:
        at = next((r.page for r in read_row if r.page is not None), None)
        page = columns.get(at) if at is not None else None
        edges = page.edges if page else []
        row_spans = spans(
            [r.boxes.get(at) if at is not None else None for r in read_row],
            edges,
            page.verticals if page else [],
        )
        slots: List[Optional[Cell]] = [None] * max(width, len(read_row))
        column = 0
        for i in sorted(range(len(row_spans)), key=lambda i: row_spans[i][0]):
            first, last = row_spans[i]
            first = max(first, column)
            last = max(last, first + 1)
            for c in range(first, min(last, len(slots))):
                slots[c] = Cell(
                    text=read_row[i].text,
                    merged=None if c == first else "left",
                    tables=read_row[i].tables if c == first else [],
                )
            column = last

        printed = [r.boxes[at] for r in read_row if at is not None and at in r.boxes]
        top: Optional[float] = min((b[1] for b in printed), default=None)
        # An empty cell with no border above it is the cell above it, again
        if at is not None and page and top is not None and above and at in bottom_above:
            ruled = pages.horizontals(at, page.extent)
            for c, slot in enumerate(slots):
                if slot is None or slot.text.strip() or slot.merged:
                    continue
                if c >= len(edges) - 1 or c >= len(above):
                    continue
                left, right = edges[c], edges[c + 1]
                if not any(
                    bottom_above[at] - 1 < y < top + 1
                    and min(x1, right) - max(x0, left) > 0.5 * (right - left)
                    for y, x0, x1 in ruled
                ):
                    slots[c] = Cell(text=above[c].text, merged="up")
        if at is not None and printed:
            bottom_above[at] = max(b[3] for b in printed)
        # A column no cell of the row covers is the cell above it, where any
        row = [
            slot
            if slot is not None
            else Cell(text=above[c].text, merged="up")
            if c < len(above)
            else Cell()
            for c, slot in enumerate(slots)
        ]
        out.append(Row(cells=row))
        placed.append(Placed(at, top, row_spans))
        above = row
    return out, placed


def orphans(
    pages: Pages,
    out: List[Row],
    placed: Sequence[Placed],
    edges: Dict[int, List[float]],
    extent: Dict[int, Box],
    used: Dict[int, Set[int]],
) -> None:
    """Text printed inside the table that the tree puts outside it, as Word
    tags the numbered list of a notes cell under the document, is put in the
    cell it is printed in"""

    for number, box in extent.items():
        page_edges = edges.get(number, [])
        if len(page_edges) < 2:
            continue
        left, right = page_edges[0], page_edges[-1]
        top, bottom = box[1], box[3]
        # The table's bottom border bounds it, below its last text
        below = [
            y
            for y, x0, x1 in pages.horizontals(number, box, pad=80)
            if y > bottom - 1 and x1 - x0 > 0.5 * (right - left)
        ]
        if below:
            bottom = min(below)
        for mcid, chars in sorted(
            (m, c) for m, c in pages.chars(number).items() if m is not None
        ):
            if mcid in used.get(number, set()):
                continue
            inside = [
                c
                for c in chars
                if left < (c["x0"] + c["x1"]) / 2 < right
                and top < (c["top"] + c["bottom"]) / 2 < bottom
            ]
            if not inside or len(inside) * 2 <= len(chars):
                continue
            across = (min(c["x0"] for c in chars) + max(c["x1"] for c in chars)) / 2
            down = min(c["top"] for c in chars)
            row_index = None
            for i, p in enumerate(placed):
                if p.page == number and p.top is not None and p.top <= down + 1:
                    row_index = i
            if row_index is None:
                continue
            text = text_of_chars(chars, y_tolerance=LINE)
            cells = out[row_index].cells
            for first, last in placed[row_index].spans:
                if (
                    last > len(page_edges) - 1
                    or not page_edges[first] <= across <= page_edges[last]
                ):
                    continue
                was = cells[first].text
                now = f"{was}\n{text}" if was else text
                for c in range(first, min(last, len(cells))):
                    if cells[c].text == was:
                        cells[c] = cells[c].model_copy(update={"text": now})
                used[number].add(mcid)
                break
