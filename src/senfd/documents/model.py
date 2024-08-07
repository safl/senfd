from pathlib import Path
from typing import ClassVar, List, Tuple

from pydantic import Field

import senfd.errors
import senfd.models
from senfd.documents.base import Converter, Document, strip_all_suffixes
from senfd.documents.enriched import EnrichedFigureDocument
from senfd.errors import Error


class ModelDocument(Document):

    SUFFIX_JSON: ClassVar[str] = ".model.document.json"
    SUFFIX_HTML: ClassVar[str] = ".model.document.html"

    FILENAME_SCHEMA: ClassVar[str] = "model.document.schema.json"
    FILENAME_HTML_TEMPLATE: ClassVar[str] = "model.document.html.jinja2"

    commands: List[senfd.models.Command] = Field(default_factory=list)

    @classmethod
    def from_enriched_figure_document_file(cls, path: Path):
        """Instantiate an 'organized' Document from a 'figure' document"""

        document, errors = FromEnrichedDocument.convert(path)
        return document


class FromEnrichedDocument(Converter):

    @staticmethod
    def is_applicable(path: Path) -> bool:
        return "".join(path.suffixes).lower() == EnrichedFigureDocument.SUFFIX_JSON

    @staticmethod
    def convert(path: Path) -> Tuple[Document, List[Error]]:
        """Instantiate an 'organized' Document from a 'figure' document"""

        errors: List[Error] = []

        enriched = EnrichedFigureDocument.model_validate_json(path.read_text())

        document = ModelDocument()
        document.meta.stem = strip_all_suffixes(path.stem)

        command_requirements = {
            name.strip().replace(" ", "_").replace("/", "").lower(): req.upper()
            for requirements in enriched.io_controller_command_set_support_requirements
            for name, req in requirements.grid.values
        }

        # Grab opcodes from command-set opcode definitions
        for cso in enriched.command_set_opcodes:
            for _, _, opcode, name, reference in cso.grid.values:
                data = {}
                data["opcode"] = int(opcode.replace("h", ""), 16)
                data["alias"] = name.strip().replace(" ", "_").replace("/", "").lower()
                data["name"] = name.strip()
                data["req"] = command_requirements.get(data["alias"], None)

                if not data["req"]:
                    errors.append(
                        senfd.errors.CannotDetermineCommandRequirement(
                            figure_nr=cso.figure_nr, message=f"Command name({name})"
                        )
                    )
                elif data["req"] not in ["O", "M", "P"]:
                    errors.append(
                        senfd.errors.CannotDetermineCommandRequirement(
                            message=f"Command name({name}); invalid req({data['req']})"
                        )
                    )

                cmd = senfd.models.Command(**data)

                document.commands.append(cmd)

                # TODO: Find dwords (sqe + cqe) and associate these with the command

        return document, errors
