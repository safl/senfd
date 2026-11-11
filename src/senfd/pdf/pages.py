# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
The pages of a PDF as drawn: the characters of each piece of marked content,
and the borders of the tables, which say what the structure tree does not,
the columns a merged cell spans. A specification published with its tracked
changes shown has its deletions on the page too, struck through; they are
not its text, and are kept apart, to be reported as an error of the document.
"""

from bisect import bisect_left, bisect_right
from collections import OrderedDict, defaultdict
from typing import Dict, List, Optional, Sequence, Tuple

import pdfplumber
from pdfplumber.utils import cluster_objects
from pdfplumber.utils import extract_text as text_of_chars

from senfd.pdf.tree import Leaf, PageId

# A box on a page: left, top, right, bottom, in points from the top left
Box = Tuple[float, float, float, float]
# A vertical border: where across, and from where to where down
Vertical = Tuple[float, float, float]
# A horizontal border: where down, and from where to where across
Horizontal = Tuple[float, float, float]

# How far apart, in points, two lines of a paragraph's text may be and still
# be one line, as a superscript footnote marker beside its word
LINE = 6
# How far apart, in points, two borders may be and still be one
NEAR = 2.5
# Where a line through a character strikes it out, as a share of its height
# from the top: below it is an underline, above it a border over the text
STRUCK = (0.35, 0.75)
# The number of pages that Pages keeps in memory. Pages reads an evicted
# page again when a figure needs it, which costs time, and each kept page
# costs memory. The pages of one figure are consecutive, so they are among
# the last pages read.
HELD = 16
# The keys that Pages keeps of each character and each rectangle: the keys
# that senfd reads, and the keys of a character that pdfplumber's
# extract_text() reads
CHAR = (
    "text", "x0", "x1", "top", "bottom", "doctop", "height", "width",
    "upright", "matrix", "mcid", "size", "fontname",
)  # fmt: skip
RECT = ("x0", "x1", "top", "bottom", "height", "width")


def turned(char: dict) -> int:
    """Which way a character is turned by 90 degrees, by its text matrix: 1
    where it reads upward, -1 downward, 0 where it is not turned. The
    'upright' pdfplumber gives does not tell: it holds for text turned by a
    matrix of zero scale along the line."""

    a, b, _, _ = char["matrix"][:4]
    if abs(b) <= abs(a):
        return 0
    return 1 if b > 0 else -1


def struck(char: dict, rules: Sequence[Horizontal]) -> bool:
    """Whether a thin horizontal line of 'rules', sorted by where down they
    are, runs through the middle of 'char', striking it out"""

    if not char.get("upright", True):
        return False
    top, height = char["top"], char["bottom"] - char["top"]
    first = bisect_left(rules, (top + STRUCK[0] * height,))
    last = bisect_right(rules, (top + STRUCK[1] * height, float("inf"), float("inf")))
    across = (char["x0"] + char["x1"]) / 2
    return any(x0 - 0.5 <= across <= x1 + 0.5 for _, x0, x1 in rules[first:last])


def counted(n: int, thing: str) -> str:
    return f"{n:,} {thing}{'' if n == 1 else 's'}"


def union(a: Optional[Box], b: Box) -> Box:
    """The box holding both 'a' and 'b'"""

    if a is None:
        return b
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def kept(obj: dict, keys: Sequence[str]) -> dict:
    return {key: obj[key] for key in keys if key in obj}


class Pages:
    """The pages of a PDF, of which the last HELD pages read are kept in
    memory: the characters of each page, grouped by marked content, and the
    page's ruled borders"""

    def __init__(self, plumb: pdfplumber.PDF, index: Dict[PageId, int]):
        self.plumb = plumb
        self.index = index
        self._chars: OrderedDict[int, Dict[Optional[int], List[dict]]] = OrderedDict()
        self._rects: OrderedDict[int, List[dict]] = OrderedDict()
        # The text struck through on each page read, a string each place
        self.struck: Dict[int, List[str]] = {}
        self._seen: set[int] = set()

    def read(self, number: int) -> None:
        if number in self._chars:
            self._chars.move_to_end(number)
            self._rects.move_to_end(number)
            return
        page = self.plumb.pages[number]
        # Word prints a strike as a thin filled rectangle; a stroked line
        # through text is a drawing's, as an arrow through its label
        rules = sorted(
            (r["top"] + r["height"] / 2, r["x0"], r["x1"])
            for r in page.rects
            if r["height"] < 2 and r["width"] > 2
        )
        by_mcid: Dict[Optional[int], List[dict]] = defaultdict(list)
        places: List[str] = []
        place = ""
        for char in page.chars:
            if struck(char, rules):
                place += char["text"]
                continue
            if place.strip():
                places.append(place.strip())
            place = ""
            by_mcid[char.get("mcid")].append(kept(char, CHAR))
        if place.strip():
            places.append(place.strip())
        if places:
            self.struck[number] = places
        self._seen.add(number)
        self._chars[number] = by_mcid
        self._rects[number] = [kept(rect, RECT) for rect in page.rects]
        page.close()  # Its characters are kept above; the rest is not needed
        if len(self._chars) > HELD:
            self._chars.popitem(last=False)
            self._rects.popitem(last=False)

    def deletions(self) -> Optional[str]:
        """What every page says struck through, as tracked changes shown
        print a deletion, or None where nothing is"""

        for number in range(len(self.plumb.pages)):
            if number not in self._seen:
                self.read(number)
        if not self.struck:
            return None
        pages = sorted(self.struck)
        places = [p for n in pages for p in self.struck[n]]
        characters = sum(len(p) for p in places)
        first = places[0] if len(places[0]) <= 60 else places[0][:57].rstrip() + "..."
        return (
            f"Text struck through, a deletion of tracked changes shown, left out: "
            f"{counted(characters, 'character')} in {counted(len(places), 'place')} "
            f"on {counted(len(pages), 'page')} of the file, the first on page "
            f"{pages[0] + 1}: '{first}'"
        )

    def chars(self, number: int) -> Dict[Optional[int], List[dict]]:
        self.read(number)
        return self._chars[number]

    def rects(self, number: int) -> List[dict]:
        self.read(number)
        return self._rects[number]

    def number(self, page: PageId) -> int:
        return self.index[page]

    def text(self, paragraphs: Sequence[Sequence[Leaf]]) -> Tuple[str, Dict[int, Box]]:
        """The text of 'paragraphs', a line each, and the box it is printed
        in on each page it is on. Text turned by 90 degrees, as the headers
        of narrow columns, is read along its turn."""

        lines: List[str] = []
        boxes: Dict[int, Box] = {}
        for paragraph in paragraphs:
            chars: List[dict] = []
            for leaf in paragraph:
                number = self.number(leaf.page)
                found = self.chars(number).get(leaf.mcid, [])
                if not found:
                    continue
                chars += found
                box = (
                    min(c["x0"] for c in found),
                    min(c["top"] for c in found),
                    max(c["x1"] for c in found),
                    max(c["bottom"] for c in found),
                )
                boxes[number] = union(boxes.get(number), box)
            if not chars:
                continue
            ways = [turned(c) for c in chars]
            if sum(1 for way in ways if way) * 2 > len(chars):
                upward = sum(ways) > 0
                across = cluster_objects(chars, lambda c: (c["x0"] + c["x1"]) / 2, 4)
                # Turned to read upward, the first line stands leftmost;
                # turned to read downward, rightmost
                for column in across if upward else reversed(across):
                    along = sorted(
                        column, key=lambda c: -c["bottom"] if upward else c["top"]
                    )
                    lines.append("".join(c["text"] for c in along).strip())
            else:
                lines.append(text_of_chars(chars, y_tolerance=LINE))
        return "\n".join(lines), boxes

    def verticals(self, number: int, box: Box, pad: float = 2.0) -> List[Vertical]:
        """The vertical borders drawn beside 'box', a segment per cell side
        joined into one where they touch"""

        _, top, _, bottom = box
        found = sorted(
            (round((r["x0"] + r["x1"]) / 2, 1), r["top"], r["bottom"])
            for r in self.rects(number)
            if r["width"] < 3
            and r["height"] > 2
            and r["bottom"] > top - pad
            and r["top"] < bottom + pad
        )
        joined: List[Vertical] = []
        for x, t, b in found:
            if joined and abs(joined[-1][0] - x) < 1 and t <= joined[-1][2] + 2:
                joined[-1] = (joined[-1][0], joined[-1][1], max(joined[-1][2], b))
            else:
                joined.append((x, t, b))
        return joined

    def horizontals(self, number: int, box: Box, pad: float = 2.0) -> List[Horizontal]:
        """The horizontal borders drawn beside 'box'"""

        _, top, _, bottom = box
        return [
            (round((r["top"] + r["bottom"]) / 2, 1), r["x0"], r["x1"])
            for r in self.rects(number)
            if r["height"] < 3
            and r["width"] > 3
            and r["bottom"] > top - pad
            and r["top"] < bottom + pad
        ]


def grid(verticals: Sequence[Vertical]) -> List[float]:
    """The columns' edges, across, as the vertical borders give them"""

    edges: List[float] = []
    for x in sorted({v[0] for v in verticals}):
        if not edges or abs(edges[-1] - x) >= NEAR:
            edges.append(x)
    return edges


def edge(edges: Sequence[float], x: Optional[float], default: int) -> int:
    """The edge nearest 'x', or 'default' where none is near it"""

    if x is None or not edges:
        return default
    nearest = min(range(len(edges)), key=lambda i: abs(edges[i] - x))
    return nearest if abs(edges[nearest] - x) < NEAR else default


def spans(
    boxes: Sequence[Optional[Box]],
    edges: Sequence[float],
    verticals: Sequence[Vertical],
) -> List[Tuple[int, int]]:
    """The columns, first and past the last, each cell of a row spans: those
    between the nearest borders left and right of its text that run alongside
    it. A cell with no text, and so no box, takes a column no other covers."""

    if len(edges) < 2:
        return [(i, i + 1) for i in range(len(boxes))]
    if len(boxes) == 1:
        return [(0, len(edges) - 1)]
    placed: List[Optional[Tuple[int, int]]] = [None] * len(boxes)
    for i, box in enumerate(boxes):
        if box is None:
            continue
        x0, top, x1, bottom = box
        height = max(bottom - top, 1.0)
        beside = [
            v[0] for v in verticals if min(v[2], bottom) - max(v[1], top) > 0.3 * height
        ]
        left = [x for x in beside if x <= x0 - 0.5]
        right = [x for x in beside if x >= x1 + 0.5]
        first = edge(
            edges,
            max(left) if left else None,
            max((j for j, e in enumerate(edges) if e <= x0 + 1.5), default=0),
        )
        last = edge(
            edges,
            min(right) if right else None,
            min(
                (j for j, e in enumerate(edges) if e >= x1 - 1.5),
                default=len(edges) - 1,
            ),
        )
        placed[i] = (first, max(last, first + 1))
    covered = {c for span in placed if span for c in range(*span)}
    free = [c for c in range(len(edges) - 1) if c not in covered]
    return [span if span else take(free, edges) for span in placed]


def take(free: List[int], edges: Sequence[float]) -> Tuple[int, int]:
    """A free column, the first not covered, or one past the last"""

    if free:
        column = free.pop(0)
        return (column, column + 1)
    return (len(edges) - 1, len(edges))
