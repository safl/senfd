# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import re
from argparse import Namespace
from pathlib import Path
from typing import ClassVar, Dict, List, Optional, Tuple

import docx
import docx.text.paragraph
from pydantic import BaseModel, Field

import senfd.schemas
import senfd.tables
from senfd.documents.base import Converter, Document, DocumentMeta
from senfd.errors import Error
from senfd.tables import Cell, Row, Table


class Figure(BaseModel):
    """
    A figure as captioned in a table-of-figures in the Specification Documents.

    This is a minimally enriched figure representation. The intent is that via regular
    expressions, it should be possible to construct instances when feeding it with
    the text from a table of figures or a table that conventionally contains a figure
    caption in the first row.

    The page number is only retrievable from table of figure captions and thus optional.
    The table data is similarly represented in a form with minimal enrichment.
    """

    REGEX_TABLE_OF_FIGURES: ClassVar[str] = (
        r"^(?P<caption>Figure\s+(?P<figure_nr>\d+)\s*:"
        r"\s*(?P<description>.*?))(?P<page_nr>\d+)?$"
    )
    REGEX_TABLE_ROW: ClassVar[str] = (
        r"^(?P<caption>Figure\s+(?P<figure_nr>\d+)\s*:" r"\s*(?P<description>.*?))$"
    )
    figure_nr: int  # Figure as numbered in the specification document
    caption: str  # The entire figure caption
    description: str  # The part of figure caption without the "Fig X:" prefix

    page_nr: Optional[int] = None
    # The number and title of the section the figure is in, as "5.2.4"
    section: Optional[str] = None
    section_title: Optional[str] = None
    table: Optional[senfd.tables.Table] = None

    @classmethod
    def from_regex(cls, regex, text):
        match = re.match(regex, text)
        if not match:
            return None

        data = {
            "figure_nr": int(match.group("figure_nr")),
            "caption": match.group("caption").strip(),
            "description": match.group("description").strip(),
        }
        if "page_nr" in match.groupdict():
            data["page_nr"] = int(match.group("page_nr"))

        return cls(**data)


class FigureDocument(Document):
    SUFFIX_JSON: ClassVar[str] = ".plain.figure.document.json"
    SUFFIX_HTML: ClassVar[str] = ".plain.figure.document.html"

    FILENAME_SCHEMA: ClassVar[str] = "plain.figure.document.schema.json"
    FILENAME_HTML_TEMPLATE: ClassVar[str] = "plain.figure.document.html.jinja2"

    figures: List[Figure] = Field(default_factory=list)


# Heading styles by the level of their heading; an annex numbers by a letter
REGEX_HEADING_STYLE = re.compile(
    r"^(?:(?:NVMe H|Heading )(?P<level>\d)|Annex(?P<annex>(?:\.1)*))$"
)
REGEX_TOC = re.compile(
    r"^(?:Annex\s+)?(?P<number>[A-Z]?[\d.]*\d|[A-Z])\.?\t(?P<title>.+?)\t\d+$"
)


def heading_level(style_name: str) -> Optional[Tuple[int, bool]]:
    """The level of a heading of 'style_name', 1 being a chapter, and whether it
    is of an annex, or None when the style is no heading's"""

    match = REGEX_HEADING_STYLE.match(style_name)
    if not match:
        return None
    if match["level"]:
        return int(match["level"]), False
    return 1 + match["annex"].count(".1"), True


class Sections:
    """
    The number and title of the section at each point of a document, by
    counting its headings, which Word numbers by itself and leaves out of their
    text; the numbers are checked against the table of contents, which has them
    """

    def __init__(self):
        self.chapters = 0
        self.annexes = 0
        self.counters: List[int] = []
        self.annex = False
        self.current: Optional[Tuple[str, str]] = None

    def heading(self, level: int, annex: bool, title: str) -> None:
        if level == 1:
            self.annex = annex
            if annex:
                self.annexes += 1
            else:
                self.chapters += 1
            self.counters = [self.annexes if annex else self.chapters]
        elif len(self.counters) >= level:
            self.counters = self.counters[:level]
            self.counters[level - 1] += 1
        else:
            # A level skipped, as a heading of level 3 right after one of 1
            self.counters += [1] * (level - len(self.counters))
        numbers = [str(n) for n in self.counters]
        if self.annex:
            numbers[0] = chr(ord("A") + self.counters[0] - 1)
        number = ".".join(numbers)
        self.current = (number, title)

    def renumber(self, number: str) -> None:
        """The current section is numbered 'number', as "1.4.2" or "B.6"; the
        sections after it count from there"""

        parts = number.split(".")
        self.annex = parts[0].isalpha()
        first = ord(parts[0]) - ord("A") + 1 if self.annex else int(parts[0])
        if self.annex:
            self.annexes = first
        else:
            self.chapters = first
        self.counters = [first] + [int(p) for p in parts[1:]]
        assert self.current
        self.current = (number, self.current[1])


def sections_of(
    docx_document,
) -> Tuple[Dict[int, Tuple[str, str]], Dict[int, Tuple[str, str]], List[Error]]:
    """
    The section of each top-level table, by its index from 1, and of each
    figure whose caption is a paragraph, by the figure's number; and the errors
    of headings whose number counted disagrees with the table of contents

    The table of contents has the numbers as the document prints them, so a
    heading it lists takes its number from there, the count going on from it;
    Word numbers headings that do not show, as a heading without text.
    """

    toc: List[Tuple[str, str]] = []
    for paragraph in docx_document.paragraphs:
        if paragraph.style is not None and paragraph.style.name.startswith("toc"):
            match = REGEX_TOC.match(paragraph.text.strip())
            if match:
                title = " ".join(match["title"].split()).lower()
                toc.append((title, match["number"].rstrip(".")))
    depth = max((number.count(".") + 1 for _, number in toc), default=0)

    errors: List[Error] = []
    sections = Sections()
    by_table: Dict[int, Tuple[str, str]] = {}
    by_caption: Dict[int, Tuple[str, str]] = {}
    table_nr = 0
    listed = 0
    for element in docx_document.element.body.iterchildren():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag == "tbl":
            table_nr += 1
            if sections.current:
                by_table[table_nr] = sections.current
            continue
        if tag != "p":
            continue
        paragraph = docx.text.paragraph.Paragraph(element, docx_document)
        style = paragraph.style.name if paragraph.style is not None else ""
        text = paragraph.text.strip()
        if style.startswith("toc"):
            continue
        level = heading_level(style)
        if level and text:
            sections.heading(*level, text)
            if level[0] <= depth and listed < len(toc):
                title, number = toc[listed]
                if title == " ".join(text.split()).lower():
                    listed += 1
                    if sections.current and sections.current[0] != number:
                        errors.append(
                            senfd.errors.Error(
                                message=(
                                    f"Section '{text}' counted as "
                                    f"{sections.current[0]}, the table of "
                                    f"contents has {number}"
                                )
                            )
                        )
                        sections.renumber(number)
            continue
        caption = Figure.from_regex(Figure.REGEX_TABLE_ROW, text)
        if caption and sections.current and style != "table of figures":
            by_caption[caption.figure_nr] = sections.current

    return by_table, by_caption, errors


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SKIPPED = {f"{W}del", f"{W}instrText", f"{W}delText"}


def text_of_paragraph(element) -> str:
    """
    The text of a paragraph element as it reads, the results of its fields
    included, as the number of "Figure 4:" when a field numbers the figure,
    which python-docx leaves out; deleted text and field codes are not text
    """

    parts = []
    for node in element.iter():
        if any(
            a.tag in SKIPPED or a.tag.endswith("}Fallback")
            for a in [node, *node.iterancestors()]
            if a is not element.getparent()
        ):
            continue
        if node.tag == f"{W}t":
            parts.append(node.text or "")
        elif node.tag in (f"{W}tab", f"{W}ptab"):
            parts.append("\t")
        elif node.tag in (f"{W}br", f"{W}cr"):
            parts.append("\n")
        elif node.tag == f"{W}noBreakHyphen":
            # As python-docx reads it; a soft hyphen shows only at a line end
            parts.append("-")
    return "".join(parts)


def text_of_cell(docx_cell) -> str:
    return "\n".join(text_of_paragraph(p._p) for p in docx_cell.paragraphs)


class FromDocx(Converter):
    @staticmethod
    def is_applicable(path: Path) -> bool:
        return path.suffix.lower() == ".docx"

    @staticmethod
    def convert(path: Path, args: Namespace) -> Tuple[FigureDocument, List[Error]]:
        def docx_table_to_table(docx_table: docx.table.Table) -> Table:
            table = Table()

            above: List = []
            for docx_row in docx_table.rows:
                row = Row()
                table.rows.append(row)

                docx_cells = docx_row.cells
                for idx, docx_cell in enumerate(docx_cells):
                    merged = None
                    if idx and docx_cell._tc is docx_cells[idx - 1]._tc:
                        merged = "left"
                    elif idx < len(above) and docx_cell._tc is above[idx]._tc:
                        merged = "up"
                    cell = Cell(
                        text=text_of_cell(docx_cell),
                        tables=[
                            docx_table_to_table(nested_table)
                            for nested_table in docx_cell.tables
                        ]
                        if merged is None
                        else [],
                        merged=merged,
                    )
                    row.cells.append(cell)
                above = list(docx_cells)

            return table

        figures: Dict[int, Figure] = {}
        errors: List[Error] = []

        docx_document = docx.Document(path)

        # Add tabular figures -- page_nr unavailable
        for table_nr, docx_table in enumerate(docx_document.tables, 1):
            # A table of one cell holding a table and no text wraps that table
            only = docx_table.rows[0].cells[0] if len(docx_table.rows) == 1 else None
            if (
                only is not None
                and len({id(c._tc) for c in docx_table.rows[0].cells}) == 1
                and len(only.tables) == 1
                and not text_of_cell(only).strip()
            ):
                docx_table = only.tables[0]
                errors.append(
                    senfd.errors.TableError(
                        table_nr=table_nr,
                        message="Table wrapped in a table of one cell; unwrapped",
                        caption="",
                    )
                )
            table = docx_table_to_table(docx_table)

            # A table holds the figures whose captions are rows of it, as when
            # the table of one figure goes on with another's caption and rows
            parts: List[Tuple[str, List[Row]]] = []
            for row in table.rows:
                texts = {c.text.strip() for c in row.cells if c.text.strip()}
                caption = next(iter(texts)) if len(texts) == 1 else ""
                if Figure.from_regex(Figure.REGEX_TABLE_ROW, caption) or not parts:
                    parts.append((caption, [row]))
                else:
                    parts[-1][1].append(row)
            if len(parts) > 1:
                errors.append(
                    senfd.errors.TableError(
                        table_nr=table_nr,
                        message=(
                            f"Table of {len(parts)} figures, by the captions in "
                            "its rows; split"
                        ),
                        caption=parts[0][0],
                    )
                )

            for caption, rows in parts:
                figure = Figure.from_regex(Figure.REGEX_TABLE_ROW, caption)
                if not figure:
                    errors.append(
                        senfd.errors.TableError(
                            table_nr=table_nr,
                            message="Caption not on the form; 'Figure X: lorem ipsum'",
                            caption=caption or rows[0].cells[0].text.strip(),
                        )
                    )
                    continue

                existing_figure = figures.get(figure.figure_nr, None)
                if existing_figure:
                    errors.append(
                        senfd.errors.FigureDuplicateNumberError(
                            figure_nr=figure.figure_nr,
                            message=f"Duplicate figure_nr({figure.figure_nr})",
                            caption_toinsert=figure.caption,
                            caption_existing=existing_figure.caption,
                        )
                    )
                    continue

                figure.table = Table(table_nr=table_nr, rows=rows)
                figures[figure.figure_nr] = figure

        # The section of each figure
        by_table, by_caption, section_errors = sections_of(docx_document)
        errors += section_errors
        for figure in figures.values():
            figure_table = figure.table.table_nr if figure.table else None
            section = by_table.get(figure_table) if figure_table else None
            figure.section, figure.section_title = section or (None, None)

        # Update tabular figures with page_nr
        # Add non-tabular figures
        # Check table-of-figure description validity
        prev = cur = None
        tof_entry = 0
        for paragraph in docx_document.paragraphs:
            assert paragraph.style is not None
            cur = paragraph.style.name

            # We exit early to avoid scanning the entire document, since we know that
            # once we are looking at a "table of figures" paragraph, then once we see
            # one that is not, then no more will arrive
            if prev == "table of figures" and cur != "table of figures":
                break
            prev = cur
            if paragraph.style.name != "table of figures":
                continue

            tof_entry += 1

            # Check whether the paragraph is a reference to a figure
            caption = paragraph.text.strip()
            figure = Figure.from_regex(Figure.REGEX_TABLE_OF_FIGURES, caption)
            if not figure:
                errors.append(
                    senfd.errors.TableOfFiguresError(
                        tof_entry_nr=tof_entry,
                        message="Does not match figure assumptions",
                        caption=caption,
                    )
                )
                continue

            if not figure.page_nr:
                errors.append(
                    senfd.errors.TableOfFiguresError(
                        tof_entry_nr=tof_entry,
                        message="Is missing <page_nr>",
                        caption=caption,
                    )
                )
                continue

            existing = figures.get(figure.figure_nr, None)
            if existing:
                existing.page_nr = figure.page_nr
                if figure.description not in existing.description:
                    errors.append(
                        senfd.errors.TableOfFiguresDescriptionMismatchError(
                            tof_entry_nr=tof_entry,
                            figure_nr=figure.figure_nr,
                            message="Table-of-figures entry does not match table row",
                            caption_tof_entry=existing.description,
                            caption_table_row=figure.description,
                        )
                    )
            else:
                figures[figure.figure_nr] = figure

        for figure in figures.values():
            if figure.section is None and figure.figure_nr in by_caption:
                figure.section, figure.section_title = by_caption[figure.figure_nr]

        return (
            FigureDocument(
                meta=DocumentMeta(stem=path.stem.replace(".", "-")),
                figures=list(figures.values()),
            ),
            errors,
        )
