"""
A generator for **yace**: the spec header of commands, from the model

For each command it writes a struct of its 16 submission queue dwords, an
integer each, or one of 64 bits for the pairs the model has fields across, and
the masks of its fields, named by the specification's acronyms and documented
with their figure, in the form **yace** links masks to fields by; its opcode;
and a function making a command of it, declared in the header and defined in
a source for the project to build. **yace** then parses the header as any
other, so the pretty-printers, the bindings and the checks apply to it.

    yace --generate senfd --generator-option senfd.prefix=spec \\
         --generator-option senfd.commands=nvm --emit capi python

The options are 'spec', the merged specification document (by default the
one in the cache, as for senfd-query), 'prefix' of every name, by default
"spec", and 'commands', a comma separated list of command sets, as "nvm", or
commands of them, as "nvm:write", by default all.

A dword described otherwise for each of conditions, as CDW13 of Write is, is
given the masks of its description of no condition, else those of its first;
the others are named in the doc of the field. A field whose bits a field
before it has, or that has no acronym, gets no mask.
"""

import re
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List, Optional, Tuple

import senfd.query
from senfd.documents.spec import Command, Dwords, SpecDocument, alias

# The dwords of the pointers, which the model has as one field across them
POINTERS = {(6, 9): "Data Pointer (DPTR)"}


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
    member: str, prefix: str, figures: List[Dwords], width: int
) -> List[Tuple[str, int, str]]:
    """The masks of the fields of 'figures', as the name, the value and the
    doc of each; a field without an acronym, of a formula, beyond 'width' or of
    bits a field before it has is left out"""

    masks: List[Tuple[str, int, str]] = []
    taken = 0
    names: Dict[str, int] = {}
    for figure in figures:
        for field in figure.fields:
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
            doc = f"{what} ({senfd.query.cite(figure.source)}); {where} of '{member}'"
            masks.append((name, value, doc))
    return masks


class SpecHeaders:
    """Writes the spec header of the commands of the model, and the source of
    the functions making them"""

    NAME = "senfd"

    def __init__(self, output: Path, options: Dict[str, str]):
        self.output = Path(output) / self.NAME
        self.output.mkdir(parents=True, exist_ok=True)
        self.options = dict(options)

    def commands(self, spec: SpecDocument) -> List[Tuple[str, Command]]:
        """The commands asked for, by the alias of their command set"""

        wanted = [w.strip() for w in self.options.get("commands", "").split(",") if w]
        chosen = []
        for set_key, command_set in spec.command_sets.items():
            for cmd_key, command in command_set.commands.items():
                if not wanted or any(
                    w in (set_key, f"{set_key}:{cmd_key}") for w in wanted
                ):
                    chosen.append((set_key, command))
        return chosen

    def generate(self):
        path = self.options.get("spec")
        spec = senfd.query.load(Path(path) if path else None)
        prefix = self.options.get("prefix", "spec")
        stem = alias(prefix)
        guard = f"{identifier(prefix)}_H"

        header: List[str] = [
            "/**",
            f" * The commands of the NVMe specifications, by {stem}",
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

        for set_key, command in self.commands(spec):
            struct = f"{stem}_{set_key}_{alias(command.name)}"
            upper = identifier(struct)
            header += [
                f"/** {command.name}, {spec.command_sets[set_key].name} command, opcode "
                f"{command.opcode:02X}h ({senfd.query.cite(command.source)}) */",
                f"#define {upper}_OPCODE 0x{command.opcode:02x}",
                "",
            ]
            fields: List[str] = []
            masks: List[Tuple[str, int, str]] = []
            for member, lower, last, ctype in members_of(command):
                width = 32 * (last - lower + 1)
                figures, others = described(command, lower, last)
                if (lower, last + 2) in POINTERS or (lower - 2, last) in POINTERS:
                    figures, others = [], []
                these = masks_of(
                    member, f"{upper}_{identifier(member)}", figures, width
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
