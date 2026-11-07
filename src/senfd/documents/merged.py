import json
from argparse import Namespace
from pathlib import Path
from typing import List, Tuple

import senfd.errors
import senfd.models
from senfd.documents.base import Converter, Document
from senfd.documents.model import ModelDocument


def add_sqe(command: senfd.models.Command, sqe: senfd.models.CommandDwordLowerUpper):
    """Add 'sqe' to the dwords of 'command', unless another document has
    described the same dwords already"""

    key = (sqe.lower, sqe.upper, sqe.condition)
    if all((have.lower, have.upper, have.condition) != key for have in command.sqe):
        command.sqe.append(sqe)


class FromFolder(Converter):
    @staticmethod
    def is_applicable(path: Path) -> bool:
        return path.is_dir() and all(path.glob(f"*{ModelDocument.SUFFIX_JSON}"))

    @staticmethod
    def convert(
        path: Path, args: Namespace
    ) -> Tuple[Document, List[senfd.errors.Error]]:
        """Instantiate an 'organized' Document from a 'figure' document"""

        errors: List[senfd.errors.Error] = []

        merged = ModelDocument()
        merged.meta.stem = "merged"

        models = [
            ModelDocument(**json.loads(path.read_text(encoding="utf-8")))
            for path in sorted(path.glob(f"*{ModelDocument.SUFFIX_JSON}"))
            if path.name != merged.json_filename()
        ]

        # A command set, as the admin commands, can be listed by more than one
        # document, each listing some of its commands
        for model in models:
            for cmdset_alias, cmdset in model.command_sets.items():
                if not cmdset.commands:
                    continue
                into = merged.command_sets.setdefault(cmdset_alias, cmdset)
                if into is cmdset:
                    continue
                for cmd_alias, command in cmdset.commands.items():
                    existing = into.commands.setdefault(cmd_alias, command)
                    if existing is not command:
                        for sqe in command.sqe:
                            add_sqe(existing, sqe)

        # The dwords of a command described in another document than the one
        # listing it
        for model in models:
            for sqe in model.sqe_of_other_documents:
                listing = [
                    cmdset.commands[sqe.command_alias]
                    for cmdset in merged.command_sets.values()
                    if sqe.command_alias in cmdset.commands
                ]
                for command in listing:
                    add_sqe(command, sqe)
                if not listing:
                    merged.sqe_of_other_documents.append(sqe)

        return merged, errors
