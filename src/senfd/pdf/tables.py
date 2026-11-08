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

from senfd.errors import Error
from senfd.pdf.pages import LINE, NEAR, Box, Pages, Vertical, grid, spans, union
from senfd.pdf.tree import Leaf, TaggedCell, paragraphs, rows
from senfd.tables import Cell, Row, Table


# How far, in points, a table's border may lie outside its text, where no
# rule separates its rows to say: the padding of a cell, with room to spare,
# but less than the margin a change bar is drawn in
PADDING = 12


class Read(NamedTuple):
    """A cell as read from the tree: its text, the box it is printed in on
    each page, the page it starts on, the tables nested in it, and the marked
    content its text is of, by paragraph"""

    text: str
    boxes: Dict[int, Box]
    page: Optional[int]
    tables: List[Table]
    paragraphs: List[List[Leaf]]


class Placed(NamedTuple):
    """Where a row is printed, and the columns each of its cells spans"""

    page: Optional[int]
    top: Optional[float]
    spans: List[Tuple[int, int]]


def table_of(
    pages: Pages,
    tagged: Sequence[Sequence[TaggedCell]],
    errors: Optional[List[Error]] = None,
) -> Tuple[List[Row], Dict[int, Box]]:
    """The rows of the table whose cells the tree gives as 'tagged', and
    where it is on each page it is on, its outer borders included. Text the
    tree puts in a cell but the page prints below the table is not the
    cell's; it is left out, and said in 'errors' where given."""

    used: Dict[int, Set[int]] = defaultdict(set)
    nested: Dict[int, List[Box]] = defaultdict(list)
    read_rows = [
        [read_cell(pages, cell, used, nested, errors) for cell in row] for row in tagged
    ]
    columns = columns_by_page(pages, read_rows, nested)
    if strays_left_out(pages, read_rows, columns, errors):
        columns = columns_by_page(pages, read_rows, nested)
    out, placed = placed_rows(pages, read_rows, columns)
    orphans(
        pages,
        out,
        placed,
        {n: c.edges for n, c in columns.items()},
        {n: c.extent for n, c in columns.items()},
        used,
    )
    extent: Dict[int, Box] = {}
    for number, column in columns.items():
        x0, top, x1, bottom = column.extent
        if column.edges:
            x0, x1 = min(x0, column.edges[0]), max(x1, column.edges[-1])
        extent[number] = (x0, top, x1, bottom)
    return out, extent


def columns_by_page(
    pages: Pages, read_rows: Sequence[Sequence[Read]], nested: Dict[int, List[Box]]
) -> Dict[int, "Columns"]:
    """The columns of the table on each page its cells are printed on"""

    by_page: Dict[int, List[Box]] = defaultdict(list)
    for read_row in read_rows:
        for read in read_row:
            for number, box in read.boxes.items():
                by_page[number].append(box)
    return {
        number: columns_of(pages, number, boxes, nested.get(number, []))
        for number, boxes in by_page.items()
    }


def astray(box: Box, columns: "Columns") -> bool:
    """Whether text printed in 'box' lies below the table whose 'columns' are
    on its page, as the heading after the table or a list of the paragraph
    after it, which Word may tag into the last cell: the table's borders say
    how far down it goes. Text beside the table is not told apart, as the
    columns found may stop short of the table's."""

    if len(columns.edges) < 2 or not columns.verticals:
        return False
    return box[1] > max(v[2] for v in columns.verticals) + LINE


def strays_left_out(
    pages: Pages,
    read_rows: List[List[Read]],
    columns: Dict[int, "Columns"],
    errors: Optional[List[Error]],
) -> bool:
    """The marked content of 'read_rows' that is astray of the table left out
    of its cell, the cell's text read again without it; whether any was"""

    found = False
    for read_row in read_rows:
        for at, read in enumerate(read_row):
            kept: List[List[Leaf]] = []
            for paragraph in read.paragraphs:
                leaves = []
                for leaf in paragraph:
                    number = pages.number(leaf.page)
                    chars = pages.chars(number).get(leaf.mcid, [])
                    column = columns.get(number)
                    if chars and column is not None:
                        box = (
                            min(c["x0"] for c in chars),
                            min(c["top"] for c in chars),
                            max(c["x1"] for c in chars),
                            max(c["bottom"] for c in chars),
                        )
                        if astray(box, column):
                            found = True
                            if errors is not None:
                                said = "".join(c["text"] for c in chars).strip()
                                errors.append(
                                    Error(
                                        message=(
                                            f"Page {number + 1} of the file: text "
                                            "tagged in a cell of a table but printed "
                                            f"outside it, left out of the cell: '{said[:60]}'"
                                        )
                                    )
                                )
                            continue
                    leaves.append(leaf)
                if leaves:
                    kept.append(leaves)
            if sum(map(len, kept)) != sum(map(len, read.paragraphs)):
                text, boxes = pages.text(kept)
                read_row[at] = read._replace(text=text, boxes=boxes, paragraphs=kept)
    return found


def read_cell(
    pages: Pages,
    cell: TaggedCell,
    used: Dict[int, Set[int]],
    nested: Dict[int, List[Box]],
    errors: Optional[List[Error]] = None,
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
        inner, inner_extent = table_of(pages, rows(element, page), errors)
        tables.append(Table(rows=inner))
        for number, (x0, top, x1, bottom) in inner_extent.items():
            nested[number].append((x0 - 3, top - 3, x1 + 3, bottom + 3))
    start: Optional[int] = next(iter(boxes), None)
    if start is None and cell.page is not None:
        start = pages.number(cell.page)
    return Read(text, boxes, start, tables, found)


class Columns(NamedTuple):
    """The columns of a table on a page: their edges, the borders giving them,
    and the extent of the table's text"""

    edges: List[float]
    verticals: List[Vertical]
    extent: Box


def columns_of(
    pages: Pages, number: int, boxes: Sequence[Box], nested: Sequence[Box]
) -> Columns:
    """The columns of the table on page 'number': the vertical borders that
    the rules separating its rows end at or cross, which a line in the margin
    beside the table, as a change bar, and the borders of a table nested in
    a cell are not. A table may be wider than its text, where a column's text
    is centred far from its border. Where no rule separates its rows, its
    borders are those beside its text."""

    extent: Optional[Box] = None
    for box in boxes:
        extent = union(extent, box)
    assert extent is not None
    separators = [
        (x0, x1)
        for y, x0, x1 in pages.horizontals(number, extent)
        if any(b[3] <= y + 1 for b in boxes) and any(b[1] >= y - 1 for b in boxes)
    ]

    def column_edge(x: float) -> bool:
        if separators:
            return any(x0 - NEAR <= x <= x1 + NEAR for x0, x1 in separators)
        return extent[0] - PADDING <= x <= extent[2] + PADDING

    verticals = [
        v
        for v in pages.verticals(number, extent)
        if column_edge(v[0])
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
