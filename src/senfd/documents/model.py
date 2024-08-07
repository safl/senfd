from pathlib import Path
from typing import ClassVar, List, Optional, Tuple

from pydantic import BaseModel, Field

import senfd.errors
from senfd.documents.base import Converter, Document, strip_all_suffixes
from senfd.documents.enriched import EnrichedFigureDocument
from senfd.errors import Error


class CommandDwords(BaseModel):
    """
    Command DWORDS; the DWORD or DWORDS forming a "field" within a command

    Should be applicable to Submission Queue Entries (SQE) as well as Completion Queuey
    Entries (CQE) since validation of DWORDS "collections" is up the the container e.g.
    (Command.sqe / Command.cqe), as the rules such as the total amount etc. needs to
    verifying at that level.
    """

    dword_lower: int
    dword_upper: int
    name: str
    acronym: str
    description: str


class Command(BaseModel):
    """Encapsulation of Command properties"""

    opcode: int
    alias: str
    name: str

    req: Optional[str]  # I/O Controller Requirement

    sqe: List[CommandDwords] = Field(default_factory=list)
    cqe: List[CommandDwords] = Field(default_factory=list)

    def is_optional(self):
        return self.requirement == "O"

    def is_mandatory(self):
        return self.requirement == "M"

    def is_prohibited(self):
        return self.requirement == "P"


class ModelDocument(Document):

    SUFFIX_JSON: ClassVar[str] = ".model.document.json"
    SUFFIX_HTML: ClassVar[str] = ".model.document.html"

    FILENAME_SCHEMA: ClassVar[str] = "model.document.schema.json"
    FILENAME_HTML_TEMPLATE: ClassVar[str] = "model.document.html.jinja2"

    commands: List[Command] = Field(default_factory=list)

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

                cmd = Command(**data)

                document.commands.append(cmd)

                # TODO: Find dwords (sqe + cqe) and associate these with the command

        return document, errors
