from pathlib import Path
from typing import ClassVar, Dict, List, Tuple

from pydantic import Field

import senfd.errors
import senfd.models
from senfd.documents.base import Converter, Document, strip_all_suffixes
from senfd.documents.enriched import EnrichedFigureDocument


class ModelDocument(Document):

    SUFFIX_JSON: ClassVar[str] = ".model.document.json"
    SUFFIX_HTML: ClassVar[str] = ".model.document.html"

    FILENAME_SCHEMA: ClassVar[str] = "model.document.schema.json"
    FILENAME_HTML_TEMPLATE: ClassVar[str] = "model.document.html.jinja2"

    command_sets: Dict[str, senfd.models.CommandSet] = Field(default_factory=dict)


class FromEnrichedDocument(Converter):

    @staticmethod
    def is_applicable(path: Path) -> bool:
        return "".join(path.suffixes).lower() == EnrichedFigureDocument.SUFFIX_JSON

    @staticmethod
    def extract_command_set(
        document: ModelDocument, enriched: EnrichedFigureDocument
    ) -> List[senfd.errors.Error]:

        errors: List[senfd.errors.Error] = []

        if not enriched.command_io_opcode:
            return errors

        # Convert I/O Opcodes and CommandSetName from the "Opcodes for ..." figure
        for item in (
            cio for cio in enriched.command_io_opcode + enriched.command_admin_opcode
        ):
            cmdset_alias = senfd.models.Command.alias_from_name(item.command_set_name)
            if not (command_set := document.command_sets.get(cmdset_alias, None)):
                command_set = senfd.models.CommandSet(
                    alias=cmdset_alias,
                    name=item.command_set_name,
                )
                document.command_sets[cmdset_alias] = command_set

            for entry in item.grid.items():
                cmd_alias = senfd.models.Command.alias_from_name(entry["command_name"])
                command_set.commands[cmd_alias] = senfd.models.Command(
                    opcode=senfd.models.Command.opcode_from_hexstr(entry["opcode"]),
                    alias=cmd_alias,
                    name=entry["command_name"],
                )

        # Process SQE figures
        for item in (sqe for sqe in enriched.command_sqe_dword):
            for command_set in document.command_sets.values():
                cmd_alias = senfd.models.Command.alias_from_name(item.command_name)
                if not (command := command_set.commands.get(cmd_alias, None)):
                    continue

                command.sqe.append(
                    senfd.models.CommandDwordLowerUpper(
                        command_alias=cmd_alias,
                        lower=item.command_dword,
                        upper=item.command_dword,
                        nbytes=4,
                        fields=[
                            senfd.models.Bits(**entry) for entry in item.grid.items()
                        ],
                    )
                )

        # Process CQE figures

        # Process data structures

        return errors

    @staticmethod
    def convert(path: Path) -> Tuple[Document, List[senfd.errors.Error]]:
        """Instantiate an 'organized' Document from a 'figure' document"""

        errors: List[senfd.errors.Error] = []
        document = ModelDocument()
        document.meta.stem = strip_all_suffixes(path.stem)

        enriched = EnrichedFigureDocument.model_validate_json(path.read_text())

        errors += FromEnrichedDocument.extract_command_set(document, enriched)

        return document, []
