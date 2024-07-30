import inspect
import re
from pathlib import Path
from typing import ClassVar, List, NamedTuple, Optional, Tuple

from pydantic import Field

import senfd.schemas
import senfd.tables
from senfd.documents.base import (
    TRANSLATION_TABLE,
    Converter,
    Document,
    strip_all_suffixes,
)
from senfd.documents.plain import Figure, FigureDocument
from senfd.utils import pascal_to_snake


class EnrichedFigure(Figure):

    @classmethod
    def from_figure_description(
        cls, figure: Figure, match
    ) -> Tuple[Optional[Figure], Optional[NamedTuple]]:
        shared = set(figure.dict().keys()).intersection(set(match.groupdict().keys()))
        if shared:
            # This occurs if child attributes overrides parent, this is an error in the
            # implementation of the child-figure
            raise RuntimeError(f"cls({cls.__name__}) has overlap({shared})")

        data = figure.dict()
        mdict = match.groupdict()
        if mdict:
            data.update(mdict if mdict else {})

        # if figure.table:
        #    table, errors = senfd.tables.HeaderTable.from_table(figure.table)
        #    data["table"] = table.dict() if table else figure.table.dict()
        enriched_figure = cls(**data)
        if figure.table:
            table, errors = senfd.tables.HeaderTable.from_table(figure.table)
            enriched_figure.table = table if table else figure.table

        return enriched_figure, errors

    def into_document(self, document):
        key = pascal_to_snake(self.__class__.__name__)
        getattr(document, key).append(self)


class Acronyms(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*Acronym\s+(definitions|Descriptions)"


class IoControllerCommandSetSupport(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r".*-\s+(?P<command_set_name>.*)Command\s+Set\s+Support"
    )
    command_set_name: str


class CnsValues(EnrichedFigure):
    """Enrichment of a: 'Command Dword N' table"""

    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*CNS\s+Values.*"


class CommandSupportRequirements(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"\s*(?P<command_span>.*)\s+Command\s*Support\s*Requirements.*"
    )
    command_span: str


class CommandSqeDataPointer(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"(?P<command_name>[\w\s]+)\s+-\s+Data\s+Pointer"
    )
    command_name: str


class CommandSqeDwords(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"(?P<command_name>[\w\s]+)\s*-\s*Command\s*Dword\s*"
        r"(?P<command_dword_lower>\d+)"
        r".*and.*?\s(?P<command_dword_upper>\d+)"
    )
    command_name: str
    command_dword_lower: str
    command_dword_upper: Optional[str]


class CommandSqeDword(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"(?P<command_name>[\w\s]+)\s*-\s*Command\s*Dword\s*(?P<command_dword>\d+).*?"
    )
    command_name: str
    command_dword: str


class CommandCqeDword(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"(?P<command_name>[\w\s]+)\s+-\s+"
        r"Completion\sQueue\sEntry\sDword\s(?P<command_dword>\d+)"
    )
    command_name: str
    command_dword: str


class CommandSetOpcodes(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"Opcodes\sfor\s(?P<command_set_name>.*)\sCommands"
    )
    command_set_name: str


class GeneralCommandStatusValues(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r".*(Generic|General)\s+Command\s+Status\s+Values.*"
    )


class CommandSpecificStatusValues(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"(?P<command_name>[\w\s]+)\s+-\s+Command\s+Specific\s+Status\s+Values"
    )
    command_name: str


class FeatureIdentifiers(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*Feature\s*Identifiers.*"


class FeatureSupport(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*Feature\s*Support.*"


class LogPageIdentifiers(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*Log\s+Page\s+Identifiers.*"


class Offset(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*offset"


class PropertyDefinition(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*Property Definition.*"


def get_figure_enriching_classes():
    """
    To avoid manually crafting a list of classes, this function
    introspectively examines this module for applicable
    classes with "REGEX_FIGURE_DESCRIPTION" class attribute.
    """
    return [
        cls
        for _, cls in inspect.getmembers(senfd.documents.enriched, inspect.isclass)
        if issubclass(cls, EnrichedFigure) and hasattr(cls, "REGEX_FIGURE_DESCRIPTION")
    ]


class EnrichedFigureDocument(Document):

    SUFFIX_JSON: ClassVar[str] = ".enriched.figure.document.json"
    SUFFIX_HTML: ClassVar[str] = ".enriched.figure.document.html"

    FILENAME_SCHEMA: ClassVar[str] = "enriched.figure.document.schema.json"
    FILENAME_HTML_TEMPLATE: ClassVar[str] = "enriched.figure.document.html.jinja2"

    nontabular: List[Figure] = Field(default_factory=list)
    uncategorized: List[Figure] = Field(default_factory=list)

    acronyms: List[Acronyms] = Field(default_factory=list)
    io_controller_command_set_support: List[IoControllerCommandSetSupport] = Field(
        default_factory=list
    )
    command_set_opcodes: List[CommandSetOpcodes] = Field(default_factory=list)
    command_support_requirements: List[CommandSupportRequirements] = Field(
        default_factory=list
    )
    command_sqe_dword: List[CommandSqeDword] = Field(default_factory=list)
    command_sqe_dwords: List[CommandSqeDwords] = Field(default_factory=list)
    command_sqe_data_pointer: List[CommandSqeDataPointer] = Field(default_factory=list)
    command_cqe_dword: List[CommandCqeDword] = Field(default_factory=list)
    command_specific_status_values: List[CommandSpecificStatusValues] = Field(
        default_factory=list
    )
    general_command_status_values: List[GeneralCommandStatusValues] = Field(
        default_factory=list
    )
    cns_values: List[CnsValues] = Field(default_factory=list)
    feature_support: List[FeatureSupport] = Field(default_factory=list)
    feature_identifiers: List[FeatureIdentifiers] = Field(default_factory=list)
    log_page_identifiers: List[LogPageIdentifiers] = Field(default_factory=list)
    offset: List[Offset] = Field(default_factory=list)
    property_definition: List[PropertyDefinition] = Field(default_factory=list)

    @classmethod
    def from_figure_document_file(cls, path: Path):
        """Instantiate an 'organized' Document from a 'figure' document"""

        document, errors = FromFigureDocument.convert(path)
        return document


class FromFigureDocument(Converter):

    @staticmethod
    def is_applicable(path: Path) -> bool:
        return "".join(path.suffixes).lower() == ".plain.figure.document.json"

    @staticmethod
    def convert(path: Path) -> Tuple[Document, List[NamedTuple]]:
        """Instantiate an 'organized' Document from a 'figure' document"""

        errors = []

        figure_document = FigureDocument.parse_file(path)

        document = EnrichedFigureDocument()
        document.meta.stem = strip_all_suffixes(path.stem)

        figure_organizers = get_figure_enriching_classes()
        for figure in figure_document.figures:
            if not figure.table:
                document.nontabular.append(figure)
                continue

            match = None
            description = figure.description.translate(TRANSLATION_TABLE)
            for candidate in figure_organizers:
                match = re.match(
                    candidate.REGEX_FIGURE_DESCRIPTION, description, flags=re.IGNORECASE
                )
                if match:
                    obj, error = candidate.from_figure_description(figure, match)
                    if error:
                        errors.append(error)
                    obj.into_document(document)
                    break

            if not match:
                document.uncategorized.append(figure)

        return document, errors
