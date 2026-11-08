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
from typing import Dict, List, NamedTuple, Optional, Tuple

import pdfplumber
import pikepdf

from senfd.documents.plain import Figure, FigureDocument
from senfd.errors import Error, FigureDuplicateNumberError
from senfd.pdf.pages import Pages
from senfd.pdf.tables import table_of
from senfd.pdf.tree import HEADINGS, paragraphs, rows, walk
from senfd.tables import Row, Table

CAPTION = re.compile(r"^Figure\s+(\d+)\s*:\s*(.*?)$", re.S)
ENTRY = re.compile(r"^Figure\s+(\d+)\s*:\s*(.*?)\s*\.*\s*(\d+)$", re.S)
NUMBERED = re.compile(r"^(?:Annex\s+)?([A-Z]?[\d.]*\d|[A-Z])\.?\s+(.*)$")
# How many rows a repeated header may have, after the caption
HEADER_ROWS = 6


class NotTagged(ValueError):
    """A PDF without a structure tree, whose tables cannot be read as data"""


class Section(NamedTuple):
    number: Optional[str]
    title: Optional[str]


def words(text: str) -> str:
    return " ".join(text.split())


def outline(pdf: pikepdf.Pdf) -> List[Section]:
    """The sections of the outline, in order, by number and title"""

    found: List[Section] = []

    def visit(items: list) -> None:
        for item in items:
            title = words(str(item.title))
            match = NUMBERED.match(title)
            found.append(Section(match[1], match[2]) if match else Section(None, title))
            visit(item.children)

    with pdf.open_outline() as tree:
        visit(tree.root)
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


def carried(row: Row) -> bool:
    """Whether 'row', the first after a page break, is the rest of the row
    before it, broken across the page: only its last cell has text"""

    texts = own(row)
    return (
        len(texts) > 1
        and texts[-1].strip() != ""
        and not any(text.strip() for text in texts[:-1])
    )


def joined(figure: Figure, table: Table) -> None:
    """'table' as the rows of 'figure' going on past a page break, without
    the caption and header rows it repeats, and with a row broken across the
    page joined again"""

    assert figure.table is not None
    heads = [heading(row) for row in figure.table.rows[: HEADER_ROWS + 1]]
    skip = 0
    for row in table.rows:
        if skip < len(heads) and heading(row) in heads:
            skip += 1
        else:
            break
    rest = table.rows[skip:]
    if rest and figure.table.rows and carried(rest[0]):
        cells = figure.table.rows[-1].cells
        start = len(cells) - 1
        while start > 0 and cells[start].merged == "left":
            start -= 1
        for cell in cells[start:]:
            cell.text = f"{cell.text}\n{rest[0].cells[-1].text}"
        rest = rest[1:]
    figure.table.rows += rest


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
        pages = Pages(plumb, {page.objgen: i for i, page in enumerate(pdf.pages)})
        numbered = outline(pdf)
        at = 0
        section = Section(None, None)
        entries: Dict[int, int] = {}
        figures: Dict[int, Figure] = {}
        last: Optional[Figure] = None
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
                found, _ = table_of(pages, rows(node.element, node.page))
                if not found:
                    continue
                table = Table(table_nr=0, rows=found)
                first = {c.text.strip() for c in found[0].cells if c.text.strip()}
                caption = words(next(iter(first))) if len(first) == 1 else ""
                match = CAPTION.match(caption)
                if not match:
                    if last is not None:  # Going on past a page break
                        joined(last, table)
                    continue
                number = int(match[1])
                if last is not None and number == last.figure_nr:
                    joined(last, table)
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
                    section=section.number,
                    section_title=section.title,
                    table=table,
                )
        for number, page in entries.items():
            if number in figures:
                figures[number].page_nr = page

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
