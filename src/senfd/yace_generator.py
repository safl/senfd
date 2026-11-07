"""
A generator for **yace**: the spec header of commands and structures, from the
model

For each command it writes a struct of its 16 submission queue dwords, an
integer each, or one of 64 bits for the pairs the model has fields across, and
the masks of its fields, named by the specification's acronyms and documented
with their figure, in the form **yace** links masks to fields by; its opcode,
in the enum of those of its command set; and a function making a command of
it, declared in the header and defined in a source for the project to build. **yace** then parses the header as any
other, so the pretty-printers, the bindings and the checks apply to it.

    yace --generate senfd --generator-option senfd.prefix=spec \\
         --generator-option senfd.commands=nvm --emit capi python

The options are 'spec', the merged specification document (by default the
one in the cache, as for senfd-query), 'prefix' of every name, by default
"spec", and 'commands', a comma separated list of command sets, as "nvm", or
commands of them, as "nvm:write", by default all.

The identifiers of the features and of the log pages, and the status codes of
each document by their type, are enums too.

It writes the data structures and log pages of the model as well, a packed
struct each, named by its document and its name, of its fields at their
offsets, the bytes no field has reserved, with the masks of the fields' bits.
The option 'structures' names others, as for 'commands', by their name or that
of their document and theirs, as "base:identify_controller", or is "none";
'flexible', if "1", makes the entries following a struct a flexible array,
which yace reports, rather than a line of its doc.

A dword described otherwise for each of conditions, as CDW13 of Write is, is
given the masks of its description of no condition, else those of its first;
the others are named in the doc of the field. A field whose bits a field
before it has, or that has no acronym, gets no mask.
"""

import re
from dataclasses import dataclass
from dataclasses import field as default
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List, Optional, Tuple, Union

import senfd.query
from senfd.documents.spec import (
    Bits,
    Command,
    Dwords,
    Entry,
    Feature,
    LogPage,
    Source,
    SpecDocument,
    Structure,
    alias,
)

# The dwords of the pointers, which the model has as one field across them
POINTERS = {(6, 9): "Data Pointer (DPTR)"}

# The C type of a field of as many bytes; one of any other size is of bytes
TYPES = {1: "uint8_t", 2: "uint16_t", 4: "uint32_t", 8: "uint64_t"}

# The kinds of structure written unless the option 'structures' says otherwise
KINDS = ("data_structure", "log_page")

# A field named by its index among fields alike, as "Power State 0 Descriptor"
INDEXED = re.compile(r"^(?P<head>.+?)\s+(?P<index>\d[\d,]*)(?P<tail>\s+\D.*)?$")


def identifier(text: str) -> str:
    """'text' as the part of a C identifier, in capitals"""

    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").upper()


def generated(headers: List[Path], sources: List[Path]):
    """What a generator wrote, as **yace** takes it; yace's own type when it is
    installed, so senfd needs no yace to be imported"""

    try:
        from yace.generators import Generated

        return Generated(headers=headers, sources=sources)
    except ImportError:
        return SimpleNamespace(headers=headers, sources=sources)


def members_of(command: Command) -> List[Tuple[str, int, int, str]]:
    """The members of the struct of 'command': the name, the first and last
    dword, and the C type of each, the pairs the model has fields across as
    one of 64 bits where they are aligned to it"""

    pairs = {
        (d.lower, d.upper)
        for d in command.sqe
        if d.upper == d.lower + 1 and d.lower % 2 == 0
    }
    members = []
    dword = 0
    while dword < 16:
        if (dword, dword + 3) in POINTERS:
            members.append((f"cdw{dword}_{dword + 1}", dword, dword + 1, "uint64_t"))
            members.append(
                (f"cdw{dword + 2}_{dword + 3}", dword + 2, dword + 3, "uint64_t")
            )
            dword += 4
        elif (dword, dword + 1) in pairs:
            members.append((f"cdw{dword}_{dword + 1}", dword, dword + 1, "uint64_t"))
            dword += 2
        else:
            members.append((f"cdw{dword}", dword, dword, "uint32_t"))
            dword += 1
    return members


def described(
    command: Command, lower: int, upper: int
) -> Tuple[List[Dwords], List[str]]:
    """The descriptions of the dwords 'lower' to 'upper' whose masks are given,
    those of no condition else those of the first, and the conditions of the
    descriptions left out"""

    these = [d for d in command.sqe if (d.lower, d.upper) == (lower, upper)]
    plain = [d for d in these if d.condition is None]
    conditions = list(dict.fromkeys(d.condition for d in these if d.condition))
    if plain:
        return plain, conditions
    if conditions:
        return [d for d in these if d.condition == conditions[0]], conditions[1:]
    return [], []


def masks_of(
    member: str,
    prefix: str,
    figures: List[Tuple[List[Bits], Source]],
    width: int,
) -> List[Tuple[str, int, str]]:
    """The masks of the fields of 'figures', each the fields of a figure and
    its source, as the name, the value and the doc of each; a field without an
    acronym, of a formula, beyond 'width', of an alternative but the first of a
    union, or of bits a field before it has is left out"""

    masks: List[Tuple[str, int, str]] = []
    taken = 0
    names: Dict[str, int] = {}
    for fields, source in figures:
        for field in fields:
            if not field.acronym or field.lower is None or field.upper is None:
                continue
            if field.upper >= width or field.union is not None and field.alternative:
                continue
            value = ((1 << (field.upper + 1)) - 1) ^ ((1 << field.lower) - 1)
            name = f"{prefix}_{identifier(field.acronym)}"
            if names.get(name) == value:
                continue
            if name in names or value & taken:
                continue
            names[name] = value
            taken |= value
            where = (
                f"bit {field.lower}"
                if field.lower == field.upper
                else f"bits {field.upper}:{field.lower}"
            )
            what = field.name or field.acronym
            doc = f"{what} ({senfd.query.cite(source)}); {where} of '{member}'"
            masks.append((name, value, doc))
    return masks


def document_key(document: str) -> str:
    """The document by the alias of its short name, as "base" """

    return alias(re.sub(r"\s+[\d.]+$", "", senfd.query.document_name(document)))


def structure_name(structure: Structure) -> str:
    """The name of 'structure' without what it is of, "Identify Controller" of
    "Identify - Identify Controller" """

    return structure.name.rsplit(" - ", 1)[-1]


def size_of(structure: Structure) -> Optional[int]:
    """The bytes of 'structure', if every field of it is at an offset given"""

    fields = [
        f for f in structure.fields if not (f.union is not None and f.alternative)
    ]
    if not fields or any(f.upper is None for f in fields):
        return None
    return max(f.upper for f in fields if f.upper is not None) + 1


@dataclass
class Member:
    """A member of the struct of a structure: 'count' is None of a scalar, 0 of
    a flexible array, else the length of an array of 'ctype'"""

    name: str
    ctype: str
    count: Optional[int]
    lower: int
    doc: str
    fields: List[Bits] = default(default_factory=list)
    size: int = 0


def index_of(field: Bits) -> Optional[int]:
    """The index 'field' is named by, as 65535 of "Stream Identifier 65,535" """

    match = INDEXED.match(field.name or "")
    return int(match["index"].replace(",", "")) if match else None


def base_of(field: Bits) -> Optional[str]:
    """The name of 'field' without its index, if it is named by one"""

    match = INDEXED.match(field.name or "")
    return f"{match['head']}{match['tail'] or ''}" if match else None


def layout_of(structure: Structure, element_of) -> Tuple[List[Member], List[str]]:
    """
    The members of the struct of 'structure', in the order of their offsets,
    and the fields left out of it, each as why

    The bytes no field has are reserved members. A run of fields named by their
    index, as "Zone Descriptor 0", "Zone Descriptor 1", of one size, is an array
    of what 'element_of' gives for their name and size: a struct of the
    structure of the name, else the bytes. A field at an offset the data gives,
    as "(NZ+1)*64", ends the struct with a flexible array, of the run it
    continues if there is one. Of a union, the first alternative is the member;
    the others are named in its doc.
    """

    fields = [
        f for f in structure.fields if not (f.union is not None and f.alternative)
    ]
    others: Dict[int, List[str]] = {}
    for f in structure.fields:
        if f.union is not None and f.alternative and f.name and f.acronym:
            others.setdefault(f.union, []).append(f"{f.name} ({f.acronym})")
    members: List[Member] = []
    left: List[str] = []
    names: Dict[str, int] = {}
    offset = 0

    def named(text: str, lower: int) -> str:
        name = text if text not in names else f"{text}_{lower}"
        names[name] = lower
        return name

    def array(base: str, size: Optional[int]) -> Tuple[str, Optional[int]]:
        """The element type of an array of 'base' and the bytes per element of
        it, as the struct of its structure or else bytes"""

        element = element_of(base, size)
        if element:
            return f"struct {element}", 1
        if size in TYPES:
            return TYPES[size], 1
        return "uint8_t", size

    index = 0
    while index < len(fields):
        f = fields[index]
        # A run is numbered from 0 or from 1, as the Result Data Structures
        first = index_of(f)
        base = base_of(f) if first in (0, 1) else None
        if f.lower is None or f.upper is None:
            ctype, _ = array(base or "", None) if base else ("uint8_t", None)
            what = base or f.name or "data"
            members.append(Member(named(alias(what), offset), ctype, 0, offset, what))
            left += [
                f"{g.name or g.range}: at an offset the data gives, in '{alias(what)}'"
                for g in fields[index + 1 :]
                if g.name
            ]
            break
        if f.lower < offset:
            left.append(f"{f.name or f.range}: of bytes a field before it has")
            index += 1
            continue
        if f.lower > offset:
            gap = f.lower - offset
            members.append(
                Member(
                    named(f"rsvd{offset}", offset),
                    "uint8_t",
                    None if gap == 1 else gap,
                    offset,
                    "Reserved",
                    size=gap,
                )
            )
            offset = f.lower
        size = f.upper - f.lower + 1
        if base and first is not None:
            # The documents leave out the rows between the first entries and
            # the last, so an entry may follow at the offset of its index
            length = 1
            following = index + 1
            while following < len(fields):
                g = fields[following]
                at = index_of(g)
                if (
                    at is None
                    or base_of(g) != base
                    or at - first < length
                    or g.lower != f.lower + (at - first) * size
                    or g.upper != g.lower + size - 1
                ):
                    break
                length = at - first + 1
                following += 1
            # Named as the acronym of the first is without its index, as PSD
            # of PSD0, else by the name without it
            stripped = re.sub(rf"{first}$", "", f.acronym or "")
            run_name = identifier(stripped).lower() if stripped else alias(base)
            rest = fields[following] if following < len(fields) else None
            if rest is not None and rest.lower is None:
                # Entries alternating with others, as a Zone Descriptor with
                # its Extension, are of no one struct
                bases = list(dict.fromkeys(filter(None, map(base_of, fields[index:]))))
                ctype, _ = array(base, size) if bases == [base] else ("uint8_t", 1)
                what = " and ".join(bases)
                members.append(Member(named(run_name, offset), ctype, 0, offset, what))
                left += [
                    f"{g.name or g.range}: at an offset the data gives, in '{run_name}'"
                    for g in fields[following + 1 :]
                    if g.name
                ]
                break
            if length > 1:
                ctype, per = array(base, size)
                members.append(
                    Member(
                        named(run_name, offset),
                        ctype,
                        length * (per or 1),
                        offset,
                        f"{base}, {length} of {size} bytes",
                        size=length * size,
                    )
                )
                offset += length * size
                index = following
                continue
        reserved = (f.name or "").lower().startswith("reserved") and not f.acronym
        if reserved:
            name = f"rsvd{f.lower}"
        elif f.acronym:
            name = identifier(f.acronym).lower()
        else:
            name = alias(f.name or f"bytes_{f.lower}")
        doc = f.name or "Reserved"
        if f.union is not None and others.get(f.union):
            doc += "; or, in the same bytes, " + ", or ".join(others[f.union])
        # A string is of bytes whatever its size, as the Firmware Revision
        scalar = size in TYPES and "ASCII" not in f.description
        ctype = TYPES[size] if scalar else "uint8_t"
        members.append(
            Member(
                named(name, f.lower),
                ctype,
                None if scalar else size,
                f.lower,
                doc,
                # Bytes within it, as of a bigger field, are no masks
                [g for g in f.fields if g.unit == "bits"] if scalar else [],
                size,
            )
        )
        offset = f.upper + 1
        index += 1
    return members, left


def number_of(entry: Entry) -> Optional[int]:
    """The number 'entry' is the value of, if it is one and not a range"""

    typed = entry.typed.get(entry.value_column)
    if typed is not None and typed.lower is not None:
        return typed.lower if typed.lower == typed.upper else None
    match = re.match(r"^\s*([0-9A-Fa-f]+)h\s*$", entry.value)
    return int(match[1], 16) if match else None


def enum_lines(name: str, doc: str, constants: List[Tuple[str, int, str]]) -> List[str]:
    """The enum 'name' of 'constants', each the name, the value and the doc;
    a name given again is left out if of the same value, else suffixed by its
    value"""

    body: List[str] = []
    seen: Dict[str, int] = {}
    for constant, value, what in constants:
        if seen.get(constant) == value:
            continue
        if constant in seen:
            constant = f"{constant}_{value:X}H"
            if constant in seen:
                continue
        seen[constant] = value
        body.append(f"\t{constant} = 0x{value:x}, ///< {what}")
    if not body:
        return []
    return ["/**", f" * {doc}", " */", f"enum {name} {{", *body, "};", ""]


class SpecHeaders:
    """Writes the spec header of the commands of the model, and the source of
    the functions making them"""

    NAME = "senfd"

    def __init__(self, output: Path, options: Dict[str, str]):
        self.output = Path(output) / self.NAME
        self.output.mkdir(parents=True, exist_ok=True)
        self.options = dict(options)

    def commands(self, spec: SpecDocument) -> List[Tuple[str, Command]]:
        """The commands asked for, by the alias of their command set, or none"""

        wanted = [w.strip() for w in self.options.get("commands", "").split(",") if w]
        if wanted == ["none"]:
            return []
        chosen = []
        for set_key, command_set in spec.command_sets.items():
            for cmd_key, command in command_set.commands.items():
                if not wanted or any(
                    w in (set_key, f"{set_key}:{cmd_key}") for w in wanted
                ):
                    chosen.append((set_key, command))
        return chosen

    def structures(self, spec: SpecDocument) -> List[Structure]:
        """The structures asked for: of the kinds of KINDS unless 'structures'
        names them, by their alias or that of their document and theirs, as
        "base:identify_controller", or is "none" """

        wanted = [w.strip() for w in self.options.get("structures", "").split(",") if w]
        if wanted == ["none"]:
            return []
        chosen = []
        for structure in spec.structures:
            if structure.unit != "bytes":
                continue
            key = alias(structure_name(structure))
            doc = document_key(structure.source.document)
            if (
                not wanted
                and structure.kind in KINDS
                or key in wanted
                or f"{doc}:{key}" in wanted
            ):
                chosen.append(structure)
        return chosen

    def write_structures(self, spec: SpecDocument, stem: str, taken: set) -> List[str]:
        """The structs of the structures asked for, and of those their arrays
        are of, each before the structs having it"""

        by_name: Dict[Tuple[str, str], List[Structure]] = {}
        for structure in spec.structures:
            if structure.unit == "bytes":
                key = (
                    document_key(structure.source.document),
                    alias(structure_name(structure)),
                )
                by_name.setdefault(key, []).append(structure)
        flexible = self.options.get("flexible", "0") not in ("0", "", "no", "false")
        lines: List[str] = []
        written: Dict[int, str] = {}
        layouts: Dict[Tuple[str, ...], str] = {}

        def write(structure: Structure) -> Optional[str]:
            if id(structure) in written:
                return written[id(structure)]
            doc = document_key(structure.source.document)

            def element_of(base: str, size: Optional[int]) -> Optional[str]:
                for key in (
                    alias(base),
                    alias(re.sub(r"\s+Data Structure$", "", base)),
                ):
                    for candidate in by_name.get((doc, key), []):
                        if (
                            candidate is not structure
                            and (size is None or size_of(candidate) == size)
                            and size_of(candidate)
                        ):
                            return write(candidate)
                return None

            members, left = layout_of(structure, element_of)
            if not [m for m in members if m.count != 0]:
                written[id(structure)] = ""
                return None
            shape = tuple(f"{m.name}:{m.ctype}:{m.count}:{m.lower}" for m in members)
            kind = "log_" if structure.kind == "log_page" else ""
            name = f"{stem}_{doc}_{kind}{alias(structure_name(structure))}"
            if shape in layouts and layouts[shape].startswith(name):
                written[id(structure)] = layouts[shape]
                return layouts[shape]
            if name in taken:
                name = f"{name}_figure{structure.source.figure_nr}"
            if name in taken:
                written[id(structure)] = ""
                return None
            taken.add(name)
            layouts[shape] = name
            written[id(structure)] = name
            upper = identifier(name)
            body: List[str] = []
            masks: List[Tuple[str, int, str]] = []
            follows: List[str] = []
            for m in members:
                if m.count == 0 and not flexible:
                    of = f", each a '{m.ctype}'" if m.ctype.startswith("struct") else ""
                    follows += [
                        f" * Followed, from byte {m.lower}, by as many {m.doc} as the"
                        f" data says{of}",
                    ]
                    continue
                where = (
                    f"byte {m.lower}"
                    if m.size == 1
                    else f"bytes {m.lower + m.size - 1}:{m.lower}"
                    if m.size
                    else f"from byte {m.lower}"
                )
                these = masks_of(
                    m.name,
                    f"{upper}_{identifier(m.name)}",
                    [(m.fields, structure.source)],
                    8 * m.size,
                )
                see = f", see {upper}_{identifier(m.name)}_*" if these else ""
                count = "" if m.count is None else f"[{m.count or ''}]"
                body.append(f"\t{m.ctype} {m.name}{count}; ///< {m.doc}, {where}{see}")
                masks += these
            doc_lines = [
                "/**",
                f" * {structure.name} ({senfd.query.cite(structure.source)})",
            ]
            if follows:
                doc_lines += [" *", *follows]
            if left:
                doc_lines += [" *", " * Not members:"]
                doc_lines += [f" * {why}" for why in left]
            lines.extend(
                [
                    *doc_lines,
                    " */",
                    f"struct __attribute__((packed)) {name} {{",
                    *body,
                    "};",
                    "",
                ]
            )
            for mask, value, doc_text in masks:
                lines.extend([f"/** {doc_text} */", f"#define {mask} 0x{value:x}"])
            if masks:
                lines.append("")
            return name

        for structure in self.structures(spec):
            write(structure)
        return lines

    def write_enums(self, spec: SpecDocument, stem: str) -> List[str]:
        """The enums of the opcodes of each command set, of the identifiers of
        the features and of the log pages, and of the status codes of each
        document by their type"""

        lines: List[str] = []
        upper = identifier(stem)
        opcodes: Dict[str, List[Tuple[str, int, str]]] = {}
        for set_key, command in self.commands(spec):
            name = identifier(f"{stem}_{set_key}_{alias(command.name)}")
            opcodes.setdefault(set_key, []).append(
                (
                    f"{name}_OPCODE",
                    command.opcode,
                    f"{command.name} ({senfd.query.cite(command.source)})",
                )
            )
        for set_key, constants in opcodes.items():
            lines += enum_lines(
                f"{stem}_{set_key}_opcode",
                f"The opcodes of the {spec.command_sets[set_key].name} commands",
                constants,
            )
        identified: List[Tuple[str, List[Union[Feature, LogPage]]]] = [
            ("feature", list(spec.features.values())),
            ("log_page", list(spec.log_pages.values())),
        ]
        for what, items in identified:
            constants = [
                (
                    f"{upper}_{identifier(what)}_{identifier(item.name)}",
                    item.identifier,
                    f"{item.name} ({senfd.query.cite(item.source)})",
                )
                for item in sorted(items, key=lambda i: i.identifier)
            ]
            lines += enum_lines(
                f"{stem}_{what}_identifier",
                f"The identifiers of the {what.replace('_', ' ')}s",
                constants,
            )
        statuses: Dict[Tuple[str, str], List[Tuple[str, int, str]]] = {}
        described: Dict[Tuple[str, str], str] = {}
        for values in spec.values:
            if (
                values.kind != "status_values"
                or (values.name or "Status Code") != "Status Code"
                or not values.qualifier
            ):
                continue
            doc = document_key(values.source.document)
            # A table of the types of status is of no type, and tables of one
            # type for each of scopes, as the I/O and the Fabrics commands, give
            # one value different meanings
            # A scope naming a command set names that of the document
            scope = values.scope
            if scope and re.search(r"Command Set( Specific)?$", scope):
                scope = None
            what = alias(values.qualifier)
            if what != "status_code_type":
                what += f"_{alias(scope)}_status" if scope else "_status"
            key = (doc, what)
            name = identifier(f"{stem}_{doc}_{what}")
            described[key] = (
                "The types of status"
                if what == "status_code_type"
                else f"The status codes of the type {values.qualifier}"
                + (f", of {scope}" if scope else "")
            )
            for entry in values.entries:
                value = number_of(entry)
                if value is None or not entry.name or alias(entry.name) == "reserved":
                    continue
                statuses.setdefault(key, []).append(
                    (
                        f"{name}_{identifier(entry.name)}",
                        value,
                        f"{entry.name} ({senfd.query.cite(values.source)})",
                    )
                )
        for (doc, what), constants in statuses.items():
            lines += enum_lines(
                f"{stem}_{doc}_{what}", described[(doc, what)], constants
            )
        return lines

    def generate(self):
        path = self.options.get("spec")
        spec = senfd.query.load(Path(path) if path else None)
        prefix = self.options.get("prefix", "spec")
        stem = alias(prefix)
        guard = f"{identifier(prefix)}_H"

        header: List[str] = [
            "/**",
            f" * The commands and data structures of the NVMe specifications, by {stem}",
            " *",
            " * Written by senfd from its model of the specifications; each name and",
            " * mask is as the figure it cites gives it.",
            " *",
            f" * @file {stem}.h",
            " */",
            f"#ifndef {guard}",
            f"#define {guard}",
            "",
            "#include <stdint.h>",
            "",
        ]
        source: List[str] = [f'#include "{stem}.h"', "", "#include <string.h>", ""]
        taken = {
            f"{stem}_{set_key}_{alias(command.name)}"
            for set_key, command in self.commands(spec)
        }
        header += self.write_enums(spec, stem)
        header += self.write_structures(spec, stem, taken)

        for set_key, command in self.commands(spec):
            struct = f"{stem}_{set_key}_{alias(command.name)}"
            upper = identifier(struct)
            fields: List[str] = []
            masks: List[Tuple[str, int, str]] = []
            for member, lower, last, ctype in members_of(command):
                width = 32 * (last - lower + 1)
                figures, others = described(command, lower, last)
                if (lower, last + 2) in POINTERS or (lower - 2, last) in POINTERS:
                    figures, others = [], []
                these = masks_of(
                    member,
                    f"{upper}_{identifier(member)}",
                    [(f.fields, f.source) for f in figures],
                    width,
                )
                what = (
                    f"Command Dword {lower}"
                    if lower == last
                    else f"Command Dwords {lower} and {last}"
                )
                if others:
                    what += "; described otherwise if " + ", or if ".join(others)
                see = f", see {upper}_{identifier(member)}_*" if these else ""
                fields.append(f"\t{ctype} {member}; ///< {what}{see}")
                masks += these
            header += [
                f"/** The submission queue entry of {command.name} */",
                f"struct {struct} {{",
                *fields,
                "};",
                "",
            ]
            for name, value, doc in masks:
                header += [f"/** {doc} */", f"#define {name} 0x{value:x}"]
            header += [
                "",
                "/**",
                f" * Make 'cmd' the command {command.name}: its opcode in Command",
                " * Dword 0, every other bit cleared",
                " *",
                " * @param cmd The command to make",
                " */",
                "void",
                f"{struct}_init(struct {struct} *cmd);",
                "",
            ]
            source += [
                "void",
                f"{struct}_init(struct {struct} *cmd)",
                "{",
                "\tmemset(cmd, 0, sizeof(*cmd));",
                f"\tcmd->cdw0 = {upper}_OPCODE;",
                "}",
                "",
            ]

        header += [f"#endif /* {guard} */", ""]
        header_path = self.output / f"{stem}.h"
        source_path = self.output / f"{stem}.c"
        header_path.write_text("\n".join(header), encoding="utf-8")
        source_path.write_text("\n".join(source), encoding="utf-8")
        return generated([header_path], [source_path])


def main(argv: Optional[List[str]] = None) -> int:
    """Write the spec header without yace, as 'senfd-header <output> [k=v ...]'"""

    import sys

    args = sys.argv[1:] if argv is None else argv
    if not args:
        print("usage: senfd-header <output> [spec=PATH] [prefix=P] [commands=C]")
        return 1
    options = dict(arg.split("=", 1) for arg in args[1:])
    wrote = SpecHeaders(Path(args[0]), options).generate()
    for path in wrote.headers + wrote.sources:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
