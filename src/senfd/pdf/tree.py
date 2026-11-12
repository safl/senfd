# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
The structure tree of a tagged PDF: its tables, rows, cells and headings, and
the marked content holding the text of each, which the page's characters are
then found by
"""

from typing import Iterator, List, NamedTuple, Optional, Tuple

import pikepdf

# A page of the PDF, by the object number and generation of its dictionary
PageId = Tuple[int, int]

HEADINGS = ("/H1", "/H2", "/H3", "/H4", "/H5", "/H6")
# Elements whose text runs on in the paragraph they are in
INLINE = ("/Span", "/Link", "/Lbl", "/Note", "/Reference")
# Elements that are a paragraph of their own
PARAGRAPHS = ("/P", "/LBody", *HEADINGS)


class Leaf(NamedTuple):
    """A piece of marked content: the characters of 'mcid' on 'page'"""

    page: PageId
    mcid: int


class Node(NamedTuple):
    """An element of the structure tree, with the page it is on and its depth"""

    name: str
    element: pikepdf.Dictionary
    page: Optional[PageId]
    depth: int


class TaggedCell(NamedTuple):
    """A cell of a row of a table, header (TH) or data (TD)"""

    kind: str
    element: pikepdf.Dictionary
    page: Optional[PageId]


def page_of(
    element: pikepdf.Dictionary, inherited: Optional[PageId]
) -> Optional[PageId]:
    """The page an element is on: its own, or the one it inherits"""

    page = element.get("/Pg")
    return page.objgen if page is not None else inherited


def kids(element: pikepdf.Object) -> List[pikepdf.Object]:
    """The children of an element, one or many"""

    k = element.get("/K") if isinstance(element, pikepdf.Dictionary) else None
    if k is None:
        return []
    return list(k) if isinstance(k, pikepdf.Array) else [k]


def paragraphs(
    element: pikepdf.Dictionary,
    page: Optional[PageId],
    nested: Optional[List[Tuple[pikepdf.Dictionary, Optional[PageId]]]] = None,
) -> List[List[Leaf]]:
    """The marked content under 'element', grouped by paragraph: the content
    of a paragraph and of what runs on in it, as a superscript footnote
    marker, is one group. A table under it is no text of it; where 'nested'
    is given, it is appended to it."""

    found: List[List[Leaf]] = []
    run: List[Leaf] = []
    for kid in kids(element):
        if not isinstance(kid, pikepdf.Dictionary):  # A marked-content number
            if page is not None:
                run.append(Leaf(page, int(kid)))
            continue
        kind = kid.get("/Type")
        if kind == "/MCR":
            mcr_page = page_of(kid, page)
            if mcr_page is not None:
                run.append(Leaf(mcr_page, int(kid["/MCID"])))
            continue
        if kind == "/OBJR":
            continue
        name = str(kid.get("/S"))
        kid_page = page_of(kid, page)
        if name == "/Table":
            if nested is not None:
                nested.append((kid, kid_page))
            continue
        below = paragraphs(kid, kid_page, nested)
        if name in INLINE:
            run += [leaf for paragraph in below for leaf in paragraph]
        elif name in PARAGRAPHS:
            found.append(run + [leaf for paragraph in below for leaf in paragraph])
            run = []
        else:
            if run:
                found.append(run)
                run = []
            found += below
    if run:
        found.append(run)
    return found


def contents(element: pikepdf.Dictionary, page: Optional[PageId]) -> List[Leaf]:
    """All marked content under 'element', including that of the tables
    nested in it at any depth"""

    found: List[Leaf] = []
    within = [(element, page)]
    while within:
        deeper: List[Tuple[pikepdf.Dictionary, Optional[PageId]]] = []
        for paragraph in paragraphs(*within.pop(0), deeper):
            found += paragraph
        within += deeper
    return found


def walk(
    element: pikepdf.Object, page: Optional[PageId] = None, depth: int = 0
) -> Iterator[Node]:
    """Every element of the tree under 'element', depth first, in reading
    order; the rows of a table are not walked, see rows()"""

    if isinstance(element, pikepdf.Array):
        for item in element:
            yield from walk(item, page, depth)
        return
    if not isinstance(element, pikepdf.Dictionary) or element.get("/S") is None:
        return
    here = page_of(element, page)
    yield Node(str(element["/S"]), element, here, depth)
    if element["/S"] != "/Table" and element.get("/K") is not None:
        yield from walk(element["/K"], here, depth + 1)


def rows(table: pikepdf.Dictionary, page: Optional[PageId]) -> List[List[TaggedCell]]:
    """The rows of a table, each the cells the structure tree gives it; a
    merged cell is one cell fewer in its row, or an empty one below"""

    found: List[List[TaggedCell]] = []

    def visit(element: pikepdf.Object, at: Optional[PageId]) -> None:
        if isinstance(element, pikepdf.Array):
            for item in element:
                visit(item, at)
            return
        if not isinstance(element, pikepdf.Dictionary):
            return
        name = element.get("/S")
        here = page_of(element, at)
        if name == "/TR":
            found.append(
                [
                    TaggedCell(str(cell["/S"]), cell, page_of(cell, here))
                    for cell in kids(element)
                    if isinstance(cell, pikepdf.Dictionary)
                    and cell.get("/S") in ("/TD", "/TH")
                ]
            )
        elif name in ("/Table", "/THead", "/TBody", "/TFoot") and "/K" in element:
            visit(element["/K"], here)

    visit(table, page)
    return found
