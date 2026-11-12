#!/usr/bin/env python3

# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

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
def heading(level, title):
    """A heading of 'level' before the figures after it, numbered by Word"""

    return ("heading", level, title)


FIGURES = [
    heading(1, "Foobar Command Set"),
    heading(2, "Foobar Commands"),
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
                # Errata: an opcode that is not a value, and the ranges of the
                # reserved opcodes, which are none
                ("0000 11b", "00b", "x", "Zing", "3.4"),
                ("0001 00b", "01b", "08h", "Foo Migrate", "3.5"),
                ("", "", "80h to FFh", "Reserved", ""),
            ],
        },
    ),
    heading(2, "Ding command"),
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
    # A command whose field selects its operations, the values in a table of
    # the field's description, each operation with its own dwords; the value
    # named as a command is no operation, its dwords the command's
    (
        f"Foo Migrate {DASH} Command Dword 10",
        dword(
            ("31:08", "Reserved"),
            (
                "07:00",
                (
                    "Select (SEL): The operation.",
                    {
                        "header": ("Value", "M/O", "Management Operation", "Reference"),
                        "rows": [
                            ("Foo Operations", LEFT, LEFT, LEFT),
                            ("0h", "M", "Foo Pause", "3.5.1"),
                            ("1h", "O", "Foo Go", "3.5.2"),
                            ("2h", "O", "Ding", "3.1"),
                        ],
                    },
                ),
            ),
        ),
    ),
    (
        f"Foo Migrate {DASH} Command Dword 12",
        dword(
            ("31:03", "Reserved"),
            (
                "02:00",
                (
                    "Mode (MODE): How to migrate.",
                    {
                        "header": ("Mode", "Description"),
                        "rows": [
                            ("000b", "Current"),
                            ("001b", "Default"),
                            ("010b to 111b", "Reserved"),
                        ],
                    },
                ),
            ),
        ),
    ),
    (
        f"Foo Pause {DASH} Command Dword 11",
        dword(("31:00", "Foo Pause Time (FPT)")),
    ),
    (
        f"Foo Go Management Operation {DASH} Command Dword 11",
        dword(("31:00", "Foo Go Speed (FGS)")),
    ),
    # Errata: a field beyond the bits of its dwords, an acronym that is not
    # one, and bits of no field
    (
        f"Ring {DASH} Command Dword 14 and Command Dword 15",
        dword(("64:00", "Ring Tail (RTL)")),
    ),
    (
        f"Ring {DASH} Command Dword 11",
        dword(("31:16", "Ring Mode (R MODE)")),
    ),
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
    heading(1, "Admin Commands"),
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
                ("0000 10b", "01b", "C5h", "No", "Foo Directive Send", "4.3"),
                ("0000 10b", "10b", "C6h", "No", "Foo Directive Receive", "4.4"),
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
            "rows": [
                ("Foo Config", "C0h", "O", "M", "NR"),
                # The forms of a requirement besides a level, and footnotes
                (
                    "Foo Mode",
                    "C1h to C3h",
                    "M 2",
                    "NOTE 3",
                    "Refer to the Bar Specification",
                ),
                ("Foo Spare", "C4h-C7h", "Reserved", "Vendor Specific", "O"),
                # An erratum: a requirement of no form
                ("Foo Odd", "C8h", "Maybe", "O", "O"),
            ],
        },
    ),
    (
        "Foobar Command Set Specification Version Descriptor Field Values",
        {
            "header": ("Specification Versions", "MJR Field", "MNR Field", "TER Field"),
            "rows": [("1.0", "1h", "0h", "0h"), ("1.1", "1h", "1h", "0h")],
        },
    ),
    heading(1, "Data Structures"),
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
        f"Status Code {DASH} Status Code Type Values",
        {
            "header": ("Value", "Description"),
            "rows": [("0h", "Generic Command Status"), ("7h", "Vendor Specific")],
        },
    ),
    (
        f"Status Code {DASH} Generic Command Status Values, Foo Commands",
        {"header": ("Value", "Description"), "rows": [("C0h", "Foo Clash")]},
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
    # Directives: their types, the operations of one, and the dwords and the
    # structure of its operations
    (
        "Directive Types",
        {
            "header": ("Directive", "Directive Type Value", "Reference"),
            "rows": [("Foo", "00h", "6.1"), ("Bar", "01h", "6.2")],
        },
    ),
    (
        f"Bar {DASH} Directive Operations",
        {
            "header": (
                "Directive Command",
                "Directive Operation Name",
                "Directive Operation Value",
                "Reference",
            ),
            "rows": [
                ("Foo Directive Receive", "Bar Report", "01h", "6.2.1"),
                ("Foo Directive Receive", "Reserved", "All other values", ""),
                ("Foo Directive Send", "Bar Reset", "01h", "6.2.2"),
            ],
        },
    ),
    (
        f"Bar Reset {DASH} Command Dword 12",
        dword(("31:16", "Reserved"), ("15:00", "Bar Reset Count (BRC)")),
    ),
    (
        f"Bar Directive {DASH} Bar Report Data Structure",
        {"header": FIELD, "rows": [("01:00", "Bar Report Length (BRL)")]},
    ),
    # A header of two rows, a header cell spanning the columns below it
    (
        "Foo Command Support Requirements",
        {
            "header": ("Command", "Combined Opcode", "Support Requirements", LEFT),
            "rows": [
                (UP, UP, "I/O", "Admin"),
                ("Foo Get", "C2h", "M", "O"),
            ],
        },
    ),
    # Tables the documents write oddly: the figure's number a field of Word,
    # the caption after an empty cell, the table wrapped in a table of one
    # cell, and the rows of the next figure in the table of this one
    (
        "Foo Numbered Layout",
        {"header": FIELD, "rows": [("03:00", "Foo Number (FNUM)")]},
    ),
    (
        "Foo Indented Layout",
        {"header": FIELD, "rows": [("03:00", "Foo Indent (FIND)")]},
    ),
    (
        "Foo Wrapped Layout",
        {"header": FIELD, "rows": [("03:00", "Foo Wrap (FWRP)")]},
    ),
    (
        "Foo Joined Layout",
        {"header": FIELD, "rows": [("03:00", "Foo First (FFST)")]},
    ),
    (
        "Foo Joining Layout",
        {"header": FIELD, "rows": [("03:00", "Foo Second (FSND)")]},
    ),
    # A union: an address of the same bytes either IPv4, with the bytes after
    # it reserved, or IPv6
    (
        "Foo Address Data Structure",
        {
            "header": FIELD,
            "rows": [
                ("00", "Foo Address Family (FAF)"),
                ("01:01", "Reserved"),
                ("17:02", "Foo IPv6 Address (FIP6)"),
                ("05:02", "Foo IPv4 Address (FIP4)"),
                ("17:06", "Reserved"),
            ],
        },
    ),
    # Fields of two structures in one table, sharing bytes but no union
    (
        "Foo Size Fields",
        {
            "header": ("Bytes", "Data Structure", "Description"),
            "rows": [
                ("07:00", "Foo Data Structure", "Foo Size (FSZ)"),
                ("07:00", "Bar Data Structure", "Bar Size (BSZ)"),
            ],
        },
    ),
    # Fields named by their index: a run of them with the rows between the
    # first and the last left out, a string, and entries as many as the data
    # says, of a structure of their name
    (
        "Foo Table Data Structure",
        {
            "header": FIELD,
            "rows": [
                ("31:00", "Foo Slot 0 Descriptor"),
                ("63:32", "Foo Slot 1 Descriptor"),
                ("...", ""),
                ("255:224", "Foo Slot 7 Descriptor"),
                ("263:256", "Foo Version (FVER): An ASCII string."),
            ],
        },
    ),
    (
        "Foo Entry Data Structure",
        {
            "header": FIELD,
            "rows": [
                ("07:00", "Foo Entry Key (FEK)"),
                (
                    "15:08",
                    (
                        "Foo Entry Pair (FEP): Two halves.",
                        {
                            "header": FIELD,
                            "rows": [
                                ("03:00", "Foo Low (FLO)"),
                                ("07:04", "Foo High (FHI)"),
                            ],
                        },
                    ),
                ),
                ("31:16", "Reserved"),
            ],
        },
    ),
    (
        "Foo List Data Structure",
        {
            "header": FIELD,
            "rows": [
                ("03:00", "Number of Foo Entries (NFE)"),
                ("15:04", "Reserved"),
                ("47:16", "Foo Entry 0"),
                ("79:48", "Foo Entry 1"),
                ("(NFE*32)+15:(NFE*32)-16", "Foo Entry NFE-1"),
            ],
        },
    ),
    # A run numbered from 1, with the rows between left out, after a byte no
    # field has
    (
        "Foo Results Data Structure",
        {
            "header": FIELD,
            "rows": [
                ("00", "Foo Result Count (FRC)"),
                ("03:02", "Foo Flags (FFL)"),
                ("07:04", "Foo Result 1 (FR1)"),
                ("11:08", "Foo Result 2 (FR2)"),
                ("...", ""),
                ("23:20", "Foo Result 5 (FR5)"),
            ],
        },
    ),
    # A register whose layout is a figure of a format it shares, under a
    # heading naming the register
    heading(2, f"Offset 18h: FOOVER {DASH} Foo Version"),
    (
        "Foo Version Descriptor",
        {
            "header": BITS,
            "rows": [
                ("31:16", "Foo Major Version (FMJR)"),
                ("15:00", "Foo Minor Version (FMNR)"),
            ],
        },
    ),
    # A table of no kind senfd knows, and a figure that is not a table
    (
        "Foo Overview",
        {"header": ("Name", "Purpose"), "rows": [("Foo", "Bar")]},
    ),
    ("Foo Architecture", None),
    heading(2, "Baz Capabilities"),
    # Bytes and the bits in them, in one table: a heading row names a range of
    # bytes, merged down over a row for each range of its bits, and a range of
    # bytes of no bits, "n/a", ends it
    (
        "Baz Capabilities Data Structure",
        {
            "header": ("Bytes", "Bits", "Description"),
            "rows": [
                ("Baz Supported", LEFT, LEFT),
                ("31:00", "255:02", "Reserved"),
                (UP, "01", "Zing Supported (ZS): Whether zing is supported."),
                (UP, "00", "Ring Supported (RS): Whether ring is supported."),
                ("Baz Enabled", LEFT, LEFT),
                ("63:32", "255:02", "Reserved"),
                (UP, "01", "Zing Enabled (ZE): Whether zing is enabled."),
                (UP, "00", "Ring Enabled (RE): Whether ring is enabled."),
                ("4095:64", "n/a", "Reserved"),
            ],
        },
    ),
    # Fields whose values another figure gives: the description names the
    # figure of the table, and where it names two, the table is the one named
    # for the field
    (
        "Qux Data Structure",
        {
            "header": BITS,
            "rows": [
                ("15:08", "Qux Type (QT): The type of the qux. Refer to Figure 95."),
                (
                    "07:00",
                    "Qux Kind (QK): This field is qux type specific (refer to "
                    "Figure 95). The kinds are those of Figure 96.",
                ),
            ],
        },
    ),
    (
        "Qux Types",
        {
            "header": ("Value", "Definition"),
            "rows": [
                ("00h", "Ding Qux: A qux that dings."),
                ("01h", "Ring Qux: A qux that rings."),
                ("02h to FFh", "Reserved"),
            ],
        },
    ),
    (
        "Qux Kinds",
        {
            "header": ("Value", "Definition"),
            "rows": [
                ("00h", "Plain: A qux of no kind."),
                ("01h", "Fancy: A qux of a kind."),
                ("02h to FFh", "Reserved"),
            ],
        },
    ),
    # Arrays of entries that another figure lays out: the entries are fields
    # numbered by their index, the rows between two of them left out. The
    # description names the figure of the entry, or only the structure.
    (
        "Qux List Data Structure",
        {
            "header": FIELD,
            "rows": [
                ("03:00", "Number of Qux Formats (NQF)"),
                (
                    "07:04",
                    "Qux Format 0 Support (QF0): The first format. The Qux "
                    "Format is defined in Figure 98, and listed by Figure 97.",
                ),
                (
                    "11:08",
                    "Qux Format 1 Support (QF1): The second format. The Qux "
                    "Format is defined in Figure 98.",
                ),
                ("...", ""),
                (
                    "35:32",
                    "Qux Format 7 Support (QF7): The last format. The Qux "
                    "Format is defined in Figure 98.",
                ),
                ("43:36", "Qux Vector 0 (QV0): This field contains a Qux Vector."),
                ("51:44", "Qux Vector 1 (QV1): This field contains a Qux Vector."),
                ("...", ""),
                ("67:60", "Qux Vector 3 (QV3): This field contains a Qux Vector."),
            ],
        },
    ),
    (
        "Qux Format Data Structure",
        {
            "header": BITS,
            "rows": [("31:16", "Reserved"), ("15:00", "Qux Size (QSZ)")],
        },
    ),
    (
        "Qux Vector",
        {
            "header": BITS,
            "rows": [("63:01", "Reserved"), ("00", "Qux Enabled (QE)")],
        },
    ),
]


def add_table(container, table, caption=None, indented=False):
    """Add 'table' to 'container', the document or a cell, with the caption in a
    first row spanning the table, as the specification documents do, or all of
    it but an empty first cell when 'indented'; a cell of LEFT or UP is merged
    with the cell to its left or above it"""

    columns = len(table["header"])
    rows = [table["header"], *table["rows"]]
    docx_table = container.add_table(rows=len(rows) + bool(caption), cols=columns)
    if caption:
        first = docx_table.rows[0].cells
        first[int(indented)].merge(first[-1]).text = caption
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


def number_headings(figures):
    """The number of each heading of 'figures', as Word numbers them"""

    counters, numbers = [], []
    for entry in figures:
        if entry[0] == "heading":
            level = entry[1]
            counters = counters[:level] + [0] * (level - len(counters[:level]))
            counters[level - 1] += 1
            numbers.append(".".join(str(c) for c in counters))
    return numbers


# A section that the table of contents numbers otherwise than counting the
# headings does, as when Word numbers a heading that does not show
TOC_NUMBERS = {
    "Data Structures": "4",
    f"Offset 18h: FOOVER {DASH} Foo Version": "4.1",
    "Baz Capabilities": "4.2",
}


def numbered_by_field(cell, number, caption):
    """Write the caption in 'cell' with the figure's number a field of Word,
    as the documents number their figures"""

    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    paragraph = cell.paragraphs[0]
    paragraph.text = ""
    paragraph.add_run("Figure ")
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), " SEQ Figure \\* ARABIC ")
    run = OxmlElement("w:r")
    text = OxmlElement("w:t")
    text.text = str(number)
    run.append(text)
    field.append(run)
    paragraph._p.append(field)
    paragraph.add_run(f": {caption}")


def with_hyphen(cell, before, after):
    """Write 'before' and 'after' in 'cell', joined by a hyphen that does not
    break, which Word writes as an element of its own"""

    from docx.oxml import OxmlElement

    paragraph = cell.paragraphs[0]
    paragraph.text = ""
    run = paragraph.add_run(before)
    run._r.append(OxmlElement("w:noBreakHyphen"))
    paragraph.add_run(after)


def write(path, figures):
    """Write the document of 'figures', and of the headings among them, to
    'path', with a table of contents and a table of figures"""

    document = docx.Document()
    document.core_properties.author = "senfd"
    document.add_heading("senfd example", 0)
    document.add_paragraph(
        "Figures of each kind senfd recognises, with made-up names and text."
    )
    for name in ["NVMe H1", "NVMe H2", "toc 1", "toc 2", "table of figures"]:
        document.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)

    headings = [entry for entry in figures if entry[0] == "heading"]
    for (_, level, title), number in zip(headings, number_headings(figures)):
        shown = TOC_NUMBERS.get(title, number)
        document.add_paragraph(f"{shown}\t{title}\t1", style=f"toc {level}")

    captions = [entry for entry in figures if entry[0] != "heading"]
    for number, (caption, _) in enumerate(captions, 1):
        document.add_paragraph(
            f"Figure {number}: {caption}\t{number}", style="table of figures"
        )

    document.add_paragraph("Figures")
    number = 0
    for entry in figures:
        if entry[0] == "heading":
            document.add_paragraph(entry[2], style=f"NVMe H{entry[1]}")
            continue
        number += 1
        caption, table = entry
        if table is None:
            document.add_paragraph(f"Figure {number}: {caption}")
            continue
        if caption == "Foo Wrapped Layout":
            wrapper = document.add_table(rows=1, cols=1)
            add_table(wrapper.cell(0, 0), table, caption=f"Figure {number}: {caption}")
        elif caption == "Foo Joining Layout":
            # In the table of the figure before it, caption and rows
            joined = document.tables[-1]
            joined.add_row().cells[0].merge(
                joined.rows[-1].cells[-1]
            ).text = f"Figure {number}: {caption}"
            for row in [table["header"], *table["rows"]]:
                cells = joined.add_row().cells
                for cell, text in zip(cells, row):
                    cell.text = text
            continue
        else:
            add_table(
                document,
                table,
                caption=f"Figure {number}: {caption}",
                indented=caption == "Foo Indented Layout",
            )
        if caption == "Foo Numbered Layout":
            numbered_by_field(document.tables[-1].cell(0, 0), number, caption)
            with_hyphen(document.tables[-1].cell(2, 1), "Foo", "Bar Number (FNUM)")
        document.add_paragraph()

    document.save(path)


if __name__ == "__main__":
    write(
        Path(sys.argv[1]) if len(sys.argv) > 1 else Path("example/example.docx"),
        FIGURES,
    )
