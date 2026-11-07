#!/usr/bin/env python3
"""
Write example/example.docx: one or more figures of every kind senfd sorts
figures into, laid out the way the specification documents lay them out, with
made-up names and text. senfd is tested on it, so that each kind of figure is
known to be handled without any specification document in the repository.

usage: python3 toolbox/example_docx.py [path]
"""

import sys
from pathlib import Path

import docx
from docx.enum.style import WD_STYLE_TYPE

# The specification documents separate a caption's parts by an en dash
DASH = "\u2013"

# A cell merged with the one to its left, or with the one above it
LEFT = "<"
UP = "^"


FIELD = ("Bytes", "Description")
BITS = ("Bits", "Description")


def dword(*rows):
    return {"header": BITS, "rows": rows}


# Each entry is (caption, table); a table is a header and rows, or None for a
# figure that is not a table. A cell is text, or a (text, table) pair of a
# cell holding a table of its own.
FIGURES = [
    # The command set: its opcodes and the dwords of its commands make up the
    # model document
    (
        "Opcodes for Foobar Command Set Commands",
        {
            "header": (
                "Function",
                "Data Transfer",
                "Combined Opcode",
                "Command",
                "Reference",
            ),
            "rows": [
                ("0000 00b", "01b", "01h", "Ding", "3.1"),
                ("0000 01b", "10b", "02h", "Dong", "3.2"),
                ("0000 10b", "00b", "04h", "Ring1", "3.3"),
            ],
        },
    ),
    (
        f"Ding {DASH} Command Dword 10",
        dword(("31:16", "Reserved"), ("15:00", "Foo Count (FCNT): How many.")),
    ),
    (
        f"Ding {DASH} Command Dword 11 if Foo Mode is set",
        dword(("31:01", "Reserved"), ("00", "Foo Mode (FM): Whether foo.")),
    ),
    (
        f"Ding {DASH} Command Dword 2 and Command Dword 3",
        dword(("63:00", "Foo Address (FADDR): Where foo is.")),
    ),
    # Without the space after the dash, as some captions are written
    (
        f"Ding {DASH}Command Dword 14 and Command Dword 15",
        dword(("63:00", "Bar Address (BADDR): Where bar is.")),
    ),
    (
        f"Ding {DASH} Data Pointer",
        {"header": BITS, "rows": [("127:00", "Data Pointer (DPTR): The data.")]},
    ),
    (
        f"Ding {DASH} Metadata Pointer",
        {"header": BITS, "rows": [("63:00", "Metadata Pointer (MPTR): The meta.")]},
    ),
    (
        f"Ding {DASH} Completion Queue Entry Dword 0",
        dword(("31:00", "Foo Result (FRES): What came of foo.")),
    ),
    (
        f"Ding {DASH} Command Specific Status Values",
        {
            "header": ("Value", "Description"),
            "rows": [("80h", "Foo Busy: Foo is busy."), ("81h", "Foo Gone")],
        },
    ),
    (
        f"Dong {DASH} Command Dword 10",
        dword(
            ("31:08", "Reserved"),
            # A row heading the rows below it, rather than bits
            ("Foo Specific", "Foo Specific"),
            ("07:00", "Bar Kind (BK): Which bar."),
        ),
    ),
    (
        f"Dong {DASH} Data Pointer",
        {"header": BITS, "rows": [("127:00", "Data Pointer (DPTR): The data.")]},
    ),
    (f"Dong {DASH} Data Buffer", {"header": FIELD, "rows": [("511:00", "Bar Data")]}),
    (f"Dong {DASH} Data", {"header": FIELD, "rows": [("03:00", "Bar Size (BSZ)")]}),
    (
        f"Ring {DASH} Command Dword 10",
        dword(("31:00", "Ring Count (RCNT): How many rings.")),
    ),
    # A command that another document lists
    (f"Zap {DASH} Command Dword 10", dword(("31:00", "Zap Count (ZCNT)"))),
    (
        f"Status Code {DASH} Generic Command Status Values, Foobar Command Set",
        {
            "header": ("Value", "Description"),
            "rows": [("C0h", "Foo Invalid: Foo is not valid.")],
        },
    ),
    # The admin commands and the identify command
    (
        "Opcodes for Admin Commands",
        {
            "header": (
                "Function",
                "Data Transfer",
                "Combined Opcode",
                "Namespace Identifier Used",
                "Command",
                "Reference",
            ),
            "rows": [
                ("0000 00b", "10b", "C2h", "Yes", "Foo Get", "4.1"),
                ("0000 01b", "01b", "C1h", "No", "Foo Set", "4.2"),
            ],
        },
    ),
    (
        f"Admin {DASH} Foo Command Support Requirements",
        {
            "header": (
                "Command",
                "Combined Opcode",
                "I/O",
                "Admin",
                "Discovery",
                "Reference",
            ),
            "rows": [("Foo Get", "C2h", "M", "O", "P", "4.1")],
        },
    ),
    (
        f"I/O Controller {DASH} Foobar Command Set Support",
        {
            "header": ("Command", "Command Support Requirements"),
            "rows": [("Ding", "M"), ("Dong", "O")],
        },
    ),
    (
        f"Identify {DASH} CNS Values",
        {
            "header": (
                "CNS Value",
                "O/M",
                "Definition",
                "NSID",
                "CNTID",
                "CSI",
                "Reference",
            ),
            "rows": [("1Ch", "O", "Foo namespace data", "Y", "N", "Y", "5.1")],
        },
    ),
    (
        "Command Dword 11 - CNS Specific Identifier",
        dword(("31:16", "Reserved"), ("15:00", "Foo Identifier (FID): Which foo.")),
    ),
    ("Command Dword 0", dword(("31:16", "Command Identifier (CID): The command."))),
    (
        f"Foo Get {DASH} Log Specific Identifier",
        dword(("15:00", "Foo Index (FIDX): Which entry.")),
    ),
    (
        f"Get Log Page {DASH} Log Page Identifiers",
        {
            "header": ("Log Page Identifier", "Log Page Name"),
            "rows": [
                ("C0h", "Foo Statistics"),
                ("C1h", "Foo Events"),
                ("C2h", "Foo Statistics (Namespace scope)"),
            ],
        },
    ),
    (
        f"Feature Identifiers {DASH} Foobar Command Set",
        {
            "header": (
                "Feature Identifier",
                "Persistent Across Power Cycle and Reset",
                "Uses Memory Buffer for Attributes",
                "Description",
                "Scope",
            ),
            "rows": [("C0h", "No", "No", "Foo Config", "Controller")],
        },
    ),
    (
        f"Foo Config {DASH} Command Dword 11",
        dword(("31:08", "Reserved"), ("07:00", "Foo Level (FLVL): How much foo.")),
    ),
    (
        "Foo Feature Requirements",
        {
            "header": (
                "Feature Name",
                "Feature Identifier",
                "I/O",
                "Admin",
                "Discovery",
            ),
            "rows": [("Foo Config", "C0h", "O", "M", "NR")],
        },
    ),
    (
        "Foobar Command Set Specification Version Descriptor Field Values",
        {
            "header": ("Specification Versions", "MJR Field", "MNR Field", "TER Field"),
            "rows": [("1.0", "1h", "0h", "0h"), ("1.1", "1h", "1h", "0h")],
        },
    ),
    # Data structures, in the forms their captions take
    (
        "Foo Statistics Data Structure",
        {
            "header": FIELD,
            "rows": [
                ("07:00", "Foo Count (FCNT): How many foos."),
                (
                    "08",
                    (
                        "Foo Attributes (FATTR): Bits of foo.",
                        {
                            "header": BITS,
                            "rows": [("7:1", "Reserved"), ("0", "Foo On (FON)")],
                        },
                    ),
                ),
                ("511:09", "Reserved"),
            ],
        },
    ),
    (
        "Identify - Foo Namespace Data Structure, Foobar Command Set Specific",
        {"header": FIELD, "rows": [("07:00", "Foo Size (FSZE): Foo blocks.")]},
    ),
    (
        "FB Format Data Structure",
        {"header": FIELD, "rows": [("01:00", "Foo Format Size (FFS)")]},
    ),
    ("Foo Statistics Log Page", {"header": FIELD, "rows": [("15:00", "Foo Reads")]}),
    (
        "Example Foo Element returned by Foo Statistics Log Page",
        {"header": FIELD, "rows": [("15:00", "Foo Reads: 2")]},
    ),
    (
        f"Foo {DASH} Create Queue Specific",
        dword(("31:16", "Foo Queue Size (FQSZ)"), ("15:00", "Reserved")),
    ),
    (
        "PRP Entry - Foo Layout",
        dword(("63:02", "Foo Page Address (FPA)"), ("01:00", "Reserved")),
    ),
    (
        f"Foo {DASH} Management Operation Specific",
        dword(("31:00", "Foo Operation (FOP)")),
    ),
    (
        "Foo Report Data for Foo Zones",
        {"header": FIELD, "rows": [("63:00", "Number of Foo Zones (NFZ)")]},
    ),
    (
        "Foo Element Types",
        {
            "header": ("Value", "Description"),
            "rows": [("0h", "Foo Element"), ("1h", "Bar Element: Not foo.")],
        },
    ),
    (
        "Foo Acronym definitions",
        {"header": ("Term", "Definition"), "rows": [("FOO", "Foo Over Ober")]},
    ),
    (
        "Asynchronous Event Information - Foo Status",
        {"header": ("Value", "Description"), "rows": [("00h", "Foo Ready")]},
    ),
    (
        f"Status Code {DASH} Foo Error Values",
        {"header": ("Value", "Description"), "rows": [("01h", "Foo Error")]},
    ),
    (
        f"Foo Management {DASH} Host Software Specified Fields",
        {"header": FIELD, "rows": [("03:00", "Foo Owner (FOWN)")]},
    ),
    (
        "Offset 10h: FOOCAP - Foo Capabilities",
        {
            "header": ("Bits", "Type", "Reset", "Description"),
            "rows": [
                ("31:16", "RO", "0h", "Reserved"),
                ("15:00", "RW", "0h", "Foo Limit (FL): The limit."),
            ],
        },
    ),
    (
        f"Foo Get {DASH} Foo Specific Fields",
        dword(("31:00", "Foo Option (FOPT)")),
    ),
    (
        "Foo Submission Queue Entry",
        {"header": FIELD, "rows": [("63:00", "Foo Command (FCMD)")]},
    ),
    ("Foo Descriptor", {"header": FIELD, "rows": [("15:00", "Foo Key (FKEY)")]}),
    (
        "Completion Queue Entry Layout - Foo",
        {"header": FIELD, "rows": [("15:00", "Foo Status (FSTS)")]},
    ),
    (
        "Foo Property Definition",
        {
            "header": (
                "Offset (OFST)",
                "Size (in bytes)",
                "I/O Controller",
                "Administrative Controller",
                "Discovery Controller",
                "Name",
            ),
            "rows": [("00h", "8", "M", "M", "M", "Foo Capabilities (FCAP)")],
        },
    ),
    (
        "Foo Event Data Format (Event Type 02h)",
        {"header": FIELD, "rows": [("03:00", "Foo Event Count (FEC)")]},
    ),
    (
        "RPMB - Foo Write Flow",
        {
            "header": (
                "Command",
                "Bytes in Command",
                "Field Name",
                "Value",
                "Objective",
            ),
            "rows": [("Foo Set", "511:00", "Foo Key", "1234h", "Write foo")],
        },
    ),
    (
        "Foo State Transition Conditions",
        {
            "header": ("Starting", "Ending", "Transition Condition"),
            "rows": [("Idle", "Busy", "A foo arrives")],
        },
    ),
    ("Foo Response", {"header": FIELD, "rows": [("03:00", "Foo Reply (FRPL)")]}),
    (
        "Foo Attributes Entry",
        {"header": FIELD, "rows": [("01:00", "Foo Attribute (FATR)")]},
    ),
    (
        "Additional Hardware Error Information - Foo",
        {"header": FIELD, "rows": [("07:00", "Foo Error Address (FEA)")]},
    ),
    (
        "Foo Request Fields",
        {"header": FIELD, "rows": [("03:00", "Foo Tag (FTAG)")]},
    ),
    (
        "NVMe Management Foo - NVMe Management Dword 0",
        dword(("31:00", "Foo Selector (FSEL)")),
    ),
    ("Foo - PCIe Request Dword 1", dword(("31:00", "Foo Length (FLEN)"))),
    (
        "Foo Request PDU (FooReq)",
        {
            "header": ("Bytes", "PDU Section", "Description"),
            "rows": [("07:00", "PDU Header", "Foo Header")],
        },
    ),
    (
        "Foo to Bar Mapping Table",
        {
            "header": ("Bytes", "Description", "Bytes", "Description"),
            "rows": [("03:00", "Foo Word", "07:04", "Bar Word (BW)")],
        },
    ),
    # The variants the documents write the same thing in: footnote markers on
    # headers and acronyms, a reserved row merged across columns, a heading row,
    # the header again after a page break, a range continued in the row below,
    # ranges by formula, a note, and a name with no colon after it
    (
        "Bar Data Structure",
        {
            "header": ("Bytes", "O/M1", "Description"),
            "rows": [
                ("03:00", "M", "Bar Identifier (BID) 1: Which bar."),
                ("07:04", "Reserved", LEFT),
                ("Bar Specific", LEFT, LEFT),
                ("Bytes", "O/M1", "Description"),
                ("11:08", "O", "Bar Mode (BMOD)2: How bar runs."),
                (UP, UP, "00b: Bar is off."),
                ("N+3:N", "O", "Bar Entry (BE) The bar entry, of N bytes."),
                ("n/a", "O", "Bar Tail (BT): Not in the data."),
                # A range a note gives, and fields named by their ordinal
                ("NOTE 1", "O", "Bar Descriptor 0: The first."),
                ("...", "", ""),
                ("NOTE 1", "O", "Bar Descriptor NBD-1: The last."),
                ("Byte", "O/M1", "Description"),
                ("15:12", "O", "Ignored by the controller"),
                ("NOTES:\n1. Bar identifiers are unique.", LEFT, LEFT),
            ],
        },
    ),
    (
        "Supported Foo Operations",
        {
            "header": ("Command 1", "Command 2", "Combined Opcode", "Command"),
            "rows": [("Ding", "Dong", "05h", "Ding Dong")],
        },
    ),
    (
        f"Foo Get {DASH} Command Specific Status Values, Foo Get",
        {
            "header": ("Value", "Description"),
            "rows": [
                ("Foo Errors", LEFT),
                ("82h", "Foo Lost: Foo is lost."),
                ("Value", "Description"),
                ("83h", "Foo Late"),
                ("NOTE: Foo values are few.", LEFT),
            ],
        },
    ),
    (
        "Completion Queue Entry Dword 0 when Foo is set to 1b",
        dword(("31:00", "Foo Result (FRES)")),
    ),
    (
        f"Foo Set {DASH} Command Dword 10 {DASH} Foobar Command Set Specific Fields",
        dword(("31:00", "Foo Value (FVAL)")),
    ),
    (
        "Offset 20h: BARCTL - Bar Control",
        {
            "header": ("Bits", "Reset", "Type", "Definition"),
            "rows": [
                ("31:01", "0h", "RO", "Reserved"),
                ("00", "0h", "RW", "Bar Enable (BEN): Enables bar."),
            ],
        },
    ),
    # A table of no kind senfd knows, and a figure that is not a table
    (
        "Foo Overview",
        {"header": ("Name", "Purpose"), "rows": [("Foo", "Bar")]},
    ),
    ("Foo Architecture", None),
]


def add_table(container, table, caption=None):
    """Add 'table' to 'container', the document or a cell, with the caption in a
    first row spanning the table, as the specification documents do; a cell of
    LEFT or UP is merged with the cell to its left or above it"""

    columns = len(table["header"])
    rows = [table["header"], *table["rows"]]
    docx_table = container.add_table(rows=len(rows) + bool(caption), cols=columns)
    if caption:
        first = docx_table.rows[0].cells
        first[0].merge(first[-1]).text = caption
    offset = bool(caption)
    merges = []
    for ridx, row in enumerate(rows, offset):
        for cidx, cell in enumerate(row):
            if cell in (LEFT, UP):
                merges.append((ridx, cidx, cell))
                continue
            text, nested = cell if isinstance(cell, tuple) else (cell, None)
            docx_cell = docx_table.cell(ridx, cidx)
            docx_cell.text = text
            if nested:
                add_table(docx_cell, nested)
    for ridx, cidx, how in merges:
        other = (ridx, cidx - 1) if how == LEFT else (ridx - 1, cidx)
        text = docx_table.cell(*other).text
        docx_table.cell(*other).merge(docx_table.cell(ridx, cidx)).text = text


def write(path, figures):
    """Write the document of 'figures' to 'path'"""

    document = docx.Document()
    document.core_properties.author = "senfd"
    document.add_heading("senfd example", 0)
    document.add_paragraph(
        "Figures of each kind senfd recognises, with made-up names and text."
    )

    document.styles.add_style("table of figures", WD_STYLE_TYPE.PARAGRAPH)
    for number, (caption, _) in enumerate(figures, 1):
        document.add_paragraph(
            f"Figure {number}: {caption}\t{number}", style="table of figures"
        )

    document.add_heading("Figures", 1)
    for number, (caption, table) in enumerate(figures, 1):
        if table is None:
            document.add_paragraph(f"Figure {number}: {caption}")
            continue
        add_table(document, table, caption=f"Figure {number}: {caption}")
        document.add_paragraph()

    document.save(path)


if __name__ == "__main__":
    write(
        Path(sys.argv[1]) if len(sys.argv) > 1 else Path("example/example.docx"),
        FIGURES,
    )
