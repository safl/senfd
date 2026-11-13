# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import re
from argparse import Namespace
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Literal, Optional, Tuple

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
    # The page the figure is on in the PDF, counted from the file's first
    # page; only where it was read from a PDF
    pdf_page: Optional[int] = None
    # The number and title of the section the figure is in, as "5.2.4"
    section: Optional[str] = None
    section_title: Optional[str] = None
    # The paragraphs of its section before it that refer to it by number, as
    # "The Changed Zone List log page is defined in Figure 47."
    mentions: List[str] = Field(default_factory=list)
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
    sections: Dict[str, str] = Field(default_factory=dict)
    """The title of each numbered section, by its number as printed"""


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
) -> Tuple[
    Dict[int, Tuple[str, str]],
    Dict[int, Tuple[str, str]],
    Dict[str, str],
    List[Error],
]:
    """
    The section of each top-level table, by its index from 1, and of each
    figure whose caption is a paragraph, by the figure's number; the title of
    each section, by its number; and the errors of headings whose number
    counted disagrees with the table of contents

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
    titles: Dict[str, str] = {}
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
                                    f"Section '{text}': the headings before it "
                                    f"count {sections.current[0]}, the table of "
                                    f"contents has {number}; numbered as the "
                                    "table of contents"
                                )
                            )
                        )
                        sections.renumber(number)
            if sections.current:
                titles[sections.current[0]] = sections.current[1]
            continue
        caption = Figure.from_regex(Figure.REGEX_TABLE_ROW, text)
        if caption and sections.current and style != "table of figures":
            by_caption[caption.figure_nr] = sections.current

    return by_table, by_caption, titles, errors


def mentioning(texts: List[str], figure_nr: int) -> List[str]:
    """Of the paragraphs 'texts', those that refer to Figure 'figure_nr' by
    its number; its caption is not one"""

    pattern = re.compile(rf"\bFigure\s+{figure_nr}(?![\d:])")
    return [" ".join(t.split()) for t in texts if pattern.search(t)]


def paragraphs_before_tables(docx_document) -> Dict[int, List[str]]:
    """The text of the paragraphs before each top-level table, by its index
    from 1, since the heading or the table before it"""

    before: Dict[int, List[str]] = {}
    texts: List[str] = []
    table_nr = 0
    for element in docx_document.element.body.iterchildren():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag == "tbl":
            table_nr += 1
            before[table_nr], texts = texts, []
        elif tag == "p":
            paragraph = docx.text.paragraph.Paragraph(element, docx_document)
            style = paragraph.style.name if paragraph.style is not None else ""
            if heading_level(style):
                texts = []
            elif not style.startswith("toc") and style != "table of figures":
                texts.append(text_of_paragraph(element))
    return before


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


# The bullets of the Symbol font, as the PDF of the document shows them
BULLETS = {"\uf0b7": "\u2022"}
ROMAN = (
    (1000, "m"),
    (900, "cm"),
    (500, "d"),
    (400, "cd"),
    (100, "c"),
    (90, "xc"),
    (50, "l"),
    (40, "xl"),
    (10, "x"),
    (9, "ix"),
    (5, "v"),
    (4, "iv"),
    (1, "i"),
)


def numbered(number: int, fmt: str) -> str:
    """'number' written as Word writes a numbering of the format 'fmt': as
    letters, a, z, aa, as roman numerals, or as digits"""

    if fmt in ("lowerLetter", "upperLetter"):
        letter = chr(ord("a") + (number - 1) % 26) * ((number - 1) // 26 + 1)
        return letter.upper() if fmt == "upperLetter" else letter
    if fmt in ("lowerRoman", "upperRoman"):
        numerals, rest = "", number
        for value, numeral in ROMAN:
            while rest >= value:
                numerals, rest = numerals + numeral, rest - value
        return numerals.upper() if fmt == "upperRoman" else numerals
    return str(number)


class Numbering:
    """The labels Word shows before the paragraphs of a document's lists,
    "1.", "a)" or a bullet, which the document holds nowhere as text: they
    are counted from its numbering definitions, in the order of the
    paragraphs, a list going on wherever its paragraphs are, each list its
    own count. Found in 'labels', by the paragraph element."""

    def __init__(self, document):
        root = document.part.numbering_part.element
        self.nums = {n.get(f"{W}numId"): n for n in root.findall(f"{W}num")}
        self.abstract = {
            a.get(f"{W}abstractNumId"): a for a in root.findall(f"{W}abstractNum")
        }
        self.styles = {
            s.get(f"{W}styleId"): s
            for s in document.styles.element.findall(f"{W}style")
        }
        self.counters: Dict[str, Dict[int, int]] = {}
        self.labels: Dict[Any, str] = {}
        for paragraph in document.element.body.iter(f"{W}p"):
            if any(a.tag.endswith("}Fallback") for a in paragraph.iterancestors()):
                continue
            numbering = self.numbering_of(paragraph)
            if numbering is not None:
                label = self.label(*numbering)
                if label:
                    self.labels[paragraph] = label

    def style_numbering(self, style_id: Optional[str], depth: int = 0):
        """The numbering a style gives its paragraphs, its own or that of the
        style it is based on"""

        style = self.styles.get(style_id) if style_id else None
        if style is None or depth > 12:
            return None
        pPr = style.find(f"{W}pPr")
        numPr = pPr.find(f"{W}numPr") if pPr is not None else None
        if numPr is not None:
            return numPr
        based = style.find(f"{W}basedOn")
        return (
            self.style_numbering(based.get(f"{W}val"), depth + 1)
            if based is not None
            else None
        )

    def numbering_of(self, paragraph) -> Optional[Tuple[str, int]]:
        """The list a paragraph is in and its level in it, by its own
        numbering or, for what that leaves unsaid, its style's; None where it
        is in no list"""

        pPr = paragraph.find(f"{W}pPr")
        own = pPr.find(f"{W}numPr") if pPr is not None else None
        style = pPr.find(f"{W}pStyle") if pPr is not None else None
        styled = (
            self.style_numbering(style.get(f"{W}val")) if style is not None else None
        )
        num = level = None
        for numPr in (own, styled):
            if numPr is None:
                continue
            if num is None:
                num = numPr.find(f"{W}numId")
            if level is None:
                level = numPr.find(f"{W}ilvl")
        if num is None or num.get(f"{W}val") in (None, "0"):
            return None
        return num.get(f"{W}val"), int(level.get(f"{W}val")) if level is not None else 0

    def level(self, num_id: str, ilvl: int):
        """The definition of level 'ilvl' of list 'num_id', the list's own
        where it overrides the level, else its abstract numbering's, and the
        number the list starts the level over at, where it says"""

        num = self.nums.get(num_id)
        if num is None:
            return None, None
        start_over = None
        for override in num.findall(f"{W}lvlOverride"):
            if override.get(f"{W}ilvl") != str(ilvl):
                continue
            said = override.find(f"{W}startOverride")
            if said is not None:
                start_over = int(said.get(f"{W}val"))
            lvl = override.find(f"{W}lvl")
            if lvl is not None:
                return lvl, start_over
        abstract_id = num.find(f"{W}abstractNumId")
        abstract = (
            self.abstract.get(abstract_id.get(f"{W}val"))
            if abstract_id is not None
            else None
        )
        for lvl in abstract.findall(f"{W}lvl") if abstract is not None else []:
            if lvl.get(f"{W}ilvl") == str(ilvl):
                return lvl, start_over
        return None, start_over

    def first(self, num_id: str, ilvl: int) -> int:
        lvl, start_over = self.level(num_id, ilvl)
        if start_over is not None:
            return start_over
        start = lvl.find(f"{W}start") if lvl is not None else None
        return int(start.get(f"{W}val")) if start is not None else 1

    def label(self, num_id: str, ilvl: int) -> str:
        """The label of the next paragraph of list 'num_id' at level 'ilvl':
        the level counted on, the levels below it started over, and the
        level's text with each level's number written as its format says"""

        lvl, _ = self.level(num_id, ilvl)
        if lvl is None:
            return ""
        counters = self.counters.setdefault(num_id, {})
        counters[ilvl] = (
            counters[ilvl] + 1 if ilvl in counters else self.first(num_id, ilvl)
        )
        for deeper in [level for level in counters if level > ilvl]:
            del counters[deeper]
        fmt = lvl.find(f"{W}numFmt")
        text = lvl.find(f"{W}lvlText")
        said = text.get(f"{W}val", "") if text is not None else ""
        if fmt is not None and fmt.get(f"{W}val") == "bullet":
            return BULLETS.get(said, said)

        def number(match: "re.Match[str]") -> str:
            at = int(match.group(1)) - 1
            if at not in counters:
                counters[at] = self.first(num_id, at)
            higher, _ = self.level(num_id, at)
            higher_fmt = higher.find(f"{W}numFmt") if higher is not None else None
            return numbered(
                counters[at],
                higher_fmt.get(f"{W}val", "decimal")
                if higher_fmt is not None
                else "decimal",
            )

        return re.sub(r"%(\d)", number, said)


def text_of_cell(docx_cell, labels: Optional[Dict[Any, str]] = None) -> str:
    """The text of a cell, a paragraph a line, a paragraph of a list led by
    the label Word shows before it, where 'labels' has them"""

    lines = []
    for paragraph in docx_cell.paragraphs:
        text = text_of_paragraph(paragraph._p)
        label = labels.get(paragraph._p) if labels else None
        lines.append(f"{label} {text}" if label else text)
    return "\n".join(lines)


class FromPdf(Converter):
    """A tagged PDF of a specification, as NVM Express publishes it"""

    @staticmethod
    def is_applicable(path: Path) -> bool:
        return path.suffix.lower() == ".pdf"

    @staticmethod
    def convert(path: Path, args: Namespace) -> Tuple[FigureDocument, List[Error]]:
        from senfd.pdf.reader import read

        return read(path)


class FromDocx(Converter):
    @staticmethod
    def is_applicable(path: Path) -> bool:
        return path.suffix.lower() == ".docx"

    @staticmethod
    def convert(path: Path, args: Namespace) -> Tuple[FigureDocument, List[Error]]:
        labels: Dict[Any, str] = {}

        def docx_table_to_table(docx_table: docx.table.Table) -> Table:
            table = Table()

            above: List = []
            for docx_row in docx_table.rows:
                row = Row()
                table.rows.append(row)

                docx_cells = docx_row.cells
                for idx, docx_cell in enumerate(docx_cells):
                    merged: Optional[Literal["left", "up"]] = None
                    if idx and docx_cell._tc is docx_cells[idx - 1]._tc:
                        merged = "left"
                    elif idx < len(above) and docx_cell._tc is above[idx]._tc:
                        merged = "up"
                    cell = Cell(
                        text=text_of_cell(docx_cell, labels),
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

        docx_document = docx.Document(str(path))
        labels.update(Numbering(docx_document).labels)

        # Add tabular figures -- page_nr unavailable
        for table_nr, outer in enumerate(docx_document.tables, 1):
            docx_table = outer
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
                            message=(
                                "Table with no caption of the form "
                                "'Figure N: title'; its first cell is quoted"
                            ),
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
        by_table, by_caption, titles, section_errors = sections_of(docx_document)
        errors += section_errors
        before = paragraphs_before_tables(docx_document)
        for figure in figures.values():
            figure_table = figure.table.table_nr if figure.table else None
            section = by_table.get(figure_table) if figure_table else None
            figure.section, figure.section_title = section or (None, None)
            if figure_table:
                figure.mentions = mentioning(
                    before.get(figure_table, []), figure.figure_nr
                )

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

            # Check whether the paragraph is a reference to a figure; the
            # heading of the table, styled as its entries, is not one
            caption = paragraph.text.strip()
            if caption.lower() == "table of figures":
                continue
            tof_entry += 1

            figure = Figure.from_regex(Figure.REGEX_TABLE_OF_FIGURES, caption)
            if not figure:
                errors.append(
                    senfd.errors.TableOfFiguresError(
                        tof_entry_nr=tof_entry,
                        message=("Entry not of the form 'Figure N: title' and a page"),
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
                sections=titles,
            ),
            errors,
        )
