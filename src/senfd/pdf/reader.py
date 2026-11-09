# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
A tagged PDF of a specification as senfd's figure document, as a .docx is

The figures are the tables of the structure tree whose first row is a
caption, "Figure N: title", in the section of the heading before them; a
figure going on past a page break is its next table, repeating the caption
and the header rows, which are dropped, and a row broken across the page is
joined again. The section numbers are the
outline's, as printed, and the page numbers the table of figures'.
"""

import re
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

import pdfplumber
import pikepdf

from senfd.documents.plain import Figure, FigureDocument
from senfd.errors import Error, FigureDuplicateNumberError
from senfd.pdf.pages import Pages
from senfd.pdf.tables import table_of
from senfd.pdf.tree import HEADINGS, paragraphs, rows, walk
from senfd.tables import Cell, Row, Table

CAPTION = re.compile(r"^Figure\s+(\d+)\s*:\s*(.*?)$", re.S)
ENTRY = re.compile(r"^Figure\s+(\d+)\s*:\s*(.*?)\s*\.*\s*(\d+)$", re.S)
NUMBERED = re.compile(r"^(?:Annex\s+)?([A-Z]?[\d.]*\d|[A-Z])\.?\s+(.*)$")
# How many rows a repeated header may have, after the caption
HEADER_ROWS = 6


class NotTagged(ValueError):
    """A PDF without a structure tree, whose tables cannot be read as data"""


class Section(NamedTuple):
    """A section of the outline: its number and title, and where its heading
    is, the page by index and how far down it in points, by the outline's
    destination, where it has one"""

    number: Optional[str]
    title: Optional[str]
    page: Optional[int] = None
    top: Optional[float] = None


def words(text: str) -> str:
    return " ".join(text.split())


def destination(
    pdf: pikepdf.Pdf, item: pikepdf.OutlineItem, index: Dict[Tuple[int, int], int]
) -> Tuple[Optional[int], Optional[float]]:
    """The page and the place down it an outline item points at, by its
    destination, given outright or by name; None where it has none"""

    # An array, or a name to look the array up by, which may give a dictionary
    dest: object = item.destination
    if isinstance(dest, (pikepdf.Name, pikepdf.String)):
        names = pdf.Root.get("/Names")
        trees = names.get("/Dests") if names is not None else None
        plain = pdf.Root.get("/Dests")
        if trees is not None:
            dest = pikepdf.NameTree(trees).get(str(dest))
        elif plain is not None:
            dest = plain.get(str(dest))
        if isinstance(dest, pikepdf.Dictionary):
            dest = dest.get("/D")
    if not isinstance(dest, pikepdf.Array) or len(dest) < 1:
        return None, None
    page = dest[0]
    number = index.get(page.objgen) if isinstance(page, pikepdf.Dictionary) else None
    if number is None:
        return None, None
    kind = str(dest[1]) if len(dest) > 1 else ""
    at = (
        dest[3]
        if kind == "/XYZ" and len(dest) > 3
        else dest[2]
        if kind in ("/FitH", "/FitBH") and len(dest) > 2
        else None
    )
    if at is None:
        return number, 0.0
    box = pdf.pages[number].mediabox
    return number, float(box[3]) - float(at)


def outline(pdf: pikepdf.Pdf) -> List[Section]:
    """The sections of the outline, in order, by number and title, each with
    the page and place its heading is at"""

    found: List[Section] = []
    index = {page.obj.objgen: i for i, page in enumerate(pdf.pages)}

    def visit(items: list) -> None:
        for item in items:
            title = words(str(item.title))
            match = NUMBERED.match(title)
            page, top = destination(pdf, item, index)
            if match:
                found.append(Section(match[1], match[2], page, top))
            else:
                found.append(Section(None, title, page, top))
            visit(item.children)

    with pdf.open_outline() as tree:
        visit(tree.root)
    return found


def section_at(sections: Sequence[Section], page: int, top: float) -> Optional[Section]:
    """The section a figure at 'top' of page 'page' is in: the last whose
    heading the outline places before it, the deepest where several share
    the place; None where the outline places none"""

    found: Optional[Section] = None
    for section in sections:
        if section.page is None or section.top is None:
            continue
        if (section.page, section.top) <= (page, top + 1):
            if found is None or (section.page, section.top) >= (found.page, found.top):
                found = section
    return found


def own(row: Row) -> List[str]:
    """The texts of the cells of 'row', a cell spanning columns once, as it
    is the same row whatever columns a page divides it into"""

    return [cell.text for cell in row.cells if cell.merged != "left"]


def heading(row: Row) -> List[str]:
    """The texts 'row' has of its own, as a header row repeated on the next
    page is compared: without the cells merged from beside or above, which a
    page may divide or place otherwise, nor the empty ones"""

    return [c.text for c in row.cells if c.merged is None and c.text.strip()]


def last_cell(row: Row) -> Cell:
    """The last cell of 'row' as read: the first of the columns it spans,
    which holds its text and the tables nested in it"""

    at = len(row.cells) - 1
    while at > 0 and row.cells[at].merged == "left":
        at -= 1
    return row.cells[at]


def carried(row: Row) -> bool:
    """Whether 'row', the first after a page break, is the rest of the row
    before it, broken across the page: only its last cell has anything, text
    or a table nested in it"""

    texts = own(row)
    if len(texts) < 2 or any(text.strip() for text in texts[:-1]):
        return False
    return texts[-1].strip() != "" or bool(last_cell(row).tables)


def extended(previous: Table, table: Table) -> None:
    """'table' as the rows of 'previous' going on past a page break, without
    the caption and header rows it repeats, and with a row broken across the
    page joined again, its text and the tables nested in it, which go on the
    same way"""

    heads = [heading(row) for row in previous.rows[: HEADER_ROWS + 1]]
    skip = 0
    for row in table.rows:
        if skip < len(heads) and heading(row) in heads:
            skip += 1
        else:
            break
    rest = table.rows[skip:]
    if rest and previous.rows and carried(rest[0]):
        cells = previous.rows[-1].cells
        start = len(cells) - 1
        while start > 0 and cells[start].merged == "left":
            start -= 1
        more = last_cell(rest[0])
        if more.text.strip():
            for cell in cells[start:]:
                cell.text = f"{cell.text}\n{more.text}"
        for nested in more.tables:
            if cells[start].tables:
                extended(cells[start].tables[-1], nested)
            else:
                cells[start].tables.append(nested)
        rest = rest[1:]
    previous.rows += rest


def joined(figure: Figure, table: Table) -> None:
    """'table' as the rows of 'figure' going on past a page break"""

    assert figure.table is not None
    extended(figure.table, table)


def assembled(figure: Figure, pieces: List[Tuple[int, Table]]) -> None:
    """The tables of 'figure' going on past its page breaks, each with the
    page it begins on, joined in the order of their pages rather than of
    their tags: Word tags a row filling a page of its own as a table after
    the rest of the figure"""

    for _, table in sorted(pieces, key=lambda piece: piece[0]):
        joined(figure, table)


def read(path: Path) -> Tuple[FigureDocument, List[Error]]:
    """The figure document of the tagged PDF at 'path'"""

    errors: List[Error] = []
    with pikepdf.open(path) as pdf, pdfplumber.open(path) as plumb:
        root = pdf.Root.get("/StructTreeRoot")
        if root is None or root.get("/K") is None:
            raise NotTagged(
                f"{path} has no structure tree; its tables cannot be read as data. "
                "Export it from Word with the document structure tags kept, or "
                "give senfd the .docx"
            )
        pages = Pages(plumb, {page.obj.objgen: i for i, page in enumerate(pdf.pages)})
        numbered = outline(pdf)
        at = 0
        section = Section(None, None)
        entries: Dict[int, int] = {}
        figures: Dict[int, Figure] = {}
        pieces: Dict[int, List[Tuple[int, Table]]] = {}
        last: Optional[Figure] = None
        begun = 0
        for node in walk(root["/K"]):
            if node.name in HEADINGS:
                text = words(pages.text(paragraphs(node.element, node.page))[0])
                match = NUMBERED.match(text)
                title = match[2] if match else text
                number = match[1] if match else None
                # The next sections of the outline give the number as printed
                for i in range(at, min(at + 6, len(numbered))):
                    if (numbered[i].title or "").lower() == title.lower():
                        number, at = numbered[i].number, i + 1
                        break
                section = Section(number, title)
            elif node.name == "/TOCI":
                text = words(pages.text(paragraphs(node.element, node.page))[0])
                entry = ENTRY.match(text)
                if entry:
                    entries[int(entry[1])] = int(entry[3])
            elif node.name == "/Table":
                found, extent = table_of(pages, rows(node.element, node.page), errors)
                if not found:
                    continue
                # The section is the outline's, by where the table is; the
                # headings walked above stand in where the outline says not
                where = section
                if extent:  # Else it begins on the page the one before did
                    begun = min(extent)
                    placed = section_at(numbered, begun, extent[begun][1])
                    where = placed if placed is not None else section
                table = Table(table_nr=0, rows=found)
                first = {c.text.strip() for c in found[0].cells if c.text.strip()}
                caption = words(next(iter(first))) if len(first) == 1 else ""
                match = CAPTION.match(caption)
                if not match:
                    if last is not None:  # Going on past a page break
                        pieces[last.figure_nr].append((begun, table))
                    continue
                number = int(match[1])
                if last is not None and number == last.figure_nr:
                    pieces[number].append((begun, table))
                    continue
                if number in figures:
                    errors.append(
                        FigureDuplicateNumberError(
                            figure_nr=number,
                            message=f"Duplicate figure_nr({number})",
                            caption_toinsert=caption,
                            caption_existing=figures[number].caption,
                        )
                    )
                    last = None
                    continue
                table.table_nr = len(figures) + 1
                last = figures[number] = Figure(
                    figure_nr=number,
                    caption=caption,
                    description=match[2].strip(),
                    page_nr=None,
                    pdf_page=min(extent) + 1 if extent else None,
                    section=where.number,
                    section_title=where.title,
                    table=table,
                )
                pieces[number] = []
        for number, more in pieces.items():
            assembled(figures[number], more)
        for number, page in entries.items():
            if number in figures:
                figures[number].page_nr = page
        deleted = pages.deletions()
        if deleted:
            errors.append(Error(message=deleted))

    document = FigureDocument(figures=[figures[n] for n in sorted(figures)])
    document.meta.stem = stem_of(path)
    return document, errors


def stem_of(path: Path) -> str:
    """The name of the document, as the .docx of it is named: NVM Express
    names its PDFs as its .docx with hyphens for spaces, as
    'NVM Express Base Specification, Revision 2-4 Ratified 2026-07-31' of
    'NVM-Express-Base-Specification-Revision-2.4-Ratified-2026.07.31'"""

    name = path.stem
    if " " not in name:
        name = name.replace("-", " ")
    name = re.sub(r"Specification,? Revision", "Specification, Revision", name)
    return name.replace(".", "-")
