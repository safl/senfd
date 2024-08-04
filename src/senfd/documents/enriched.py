import inspect
import re
from pathlib import Path
from typing import ClassVar, List, Optional, Tuple

from pydantic import Field

import senfd.errors
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

REGEX_BITSTR_2BITS = r"(\d{2}b)"
REGEX_BITSTR_6BITS = r"(\d{4}\s\d{2}b)"
REGEX_EVERYTHING = r"(.*)"
REGEX_HEXSTR_2BYTS = r"([a-zA-Z0-9]{2}h)"

REGEX_HDR_ACRONYM = r"(Term|Acronym).*"
REGEX_HDR_BITS = r"(Bits).*"
REGEX_HDR_COMBINED_OPCODE = r"(Combined.Opcode).*"
REGEX_HDR_COMMAND = r"(Command).*"
REGEX_HDR_COMMANDS_AFFECTED = r"(Commands.Affected).*"
REGEX_HDR_DATA_TRANSFER = r"(Data.Transfer).*"
REGEX_HDR_DEFINITION = r"(Definition).*"
REGEX_HDR_DESCRIPTION = r"(Description).*"
REGEX_HDR_FUNCTION = r"(Function).*"
REGEX_HDR_REFERENCE = r"(Reference).*"
REGEX_HDR_RESET = r"(Reset).*"
REGEX_HDR_SCOPE = r"(Scope).*"
REGEX_HDR_TYPE = r"(Type).*"
REGEX_HDR_VALUE = r"(Value).*"


class EnrichedFigure(Figure):

    grid: senfd.tables.Grid = Field(default_factory=senfd.tables.Grid)

    @classmethod
    def from_figure_description(
        cls, figure: Figure, match
    ) -> Tuple[Optional[Figure], List[senfd.errors.TableError]]:
        shared = set(figure.model_dump().keys()).intersection(
            set(match.groupdict().keys())
        )
        if shared:
            # This occurs if child attributes overrides parent, this is an error in the
            # implementation of the child-figure
            raise RuntimeError(f"cls({cls.__name__}) has overlap({shared})")

        data = figure.model_dump()
        mdict = match.groupdict()
        if mdict:
            data.update(mdict if mdict else {})

        enriched_figure = cls(**data)

        grid, errors = senfd.tables.Grid.from_enriched_figure(enriched_figure)
        if grid:
            enriched_figure.grid = grid

        return enriched_figure, errors

    def into_document(self, document):
        key = pascal_to_snake(self.__class__.__name__)
        getattr(document, key).append(self)


class Acronyms(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*Acronym\s+(definitions|Descriptions)"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (REGEX_HDR_ACRONYM, REGEX_EVERYTHING),
        (REGEX_HDR_DEFINITION, REGEX_EVERYTHING),
    ]


class IoControllerCommandSetSupportRequirements(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r".*-\s+(?P<command_set_name>.*)Command\s+Set\s+Support"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (REGEX_HDR_COMMAND, "([a-zA-Z]+)"),
        (r"(Command\sSupport\sRequirements)\s\d", "(O|M|P)"),
    ]
    command_set_name: str


class CommandSupportRequirements(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"\s*(?P<command_span>.*)\s+Command\s*Support\s*Requirements.*"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (REGEX_HDR_COMMAND, "([a-zA-Z]+)"),
        (r"(Command\sSupport\sRequirements)\s\d", "(O|M|P)"),
    ]

    command_span: str


class CnsValues(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*CNS\s+Values.*"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (r"(CNS.Value)", REGEX_HEXSTR_2BYTS),
        (r"(O\/M).*", r"(O|M).*"),
        (REGEX_HDR_DEFINITION, REGEX_EVERYTHING),
        (r"(NSID).*", r"(Y|N).*"),
        (r"(CNTID).*", r"(Y|N).*"),
        (r"(CSI).*", r"(Y|N).*"),
        (REGEX_HDR_REFERENCE, REGEX_EVERYTHING),
    ]


class CommandSqeDataPointer(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"(?P<command_name>[\w\s]+)\s+-\s+Data\s+Pointer"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (REGEX_HDR_BITS, REGEX_EVERYTHING),
        (REGEX_HDR_DESCRIPTION, REGEX_EVERYTHING),
    ]

    command_name: str


class CommandSqeDwords(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"(?P<command_name>[\w\s]+)\s*-\s*Command\s*Dword\s*"
        r"(?P<command_dword_lower>\d+)"
        r".*and.*?\s(?P<command_dword_upper>\d+)"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (REGEX_HDR_BITS, REGEX_EVERYTHING),
        (REGEX_HDR_DESCRIPTION, REGEX_EVERYTHING),
    ]

    command_name: str
    command_dword_lower: str
    command_dword_upper: Optional[str]


class CommandSqeDword(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"(?P<command_name>[\w\s]+)\s*-\s*Command\s*Dword\s*(?P<command_dword>\d+).*?"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (REGEX_HDR_BITS, REGEX_EVERYTHING),
        (REGEX_HDR_DESCRIPTION, REGEX_EVERYTHING),
    ]

    command_name: str
    command_dword: str


class CommandCqeDword(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"(?P<command_name>[\w\s]+)\s+-\s+"
        r"Completion\sQueue\sEntry\sDword\s(?P<command_dword>\d+)"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (REGEX_HDR_BITS, REGEX_EVERYTHING),
        (REGEX_HDR_DESCRIPTION, REGEX_EVERYTHING),
    ]

    command_name: str
    command_dword: str


class CommandSetOpcodes(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"Opcodes\sfor\s(?P<command_set_name>.*)\sCommands"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (REGEX_HDR_FUNCTION, REGEX_BITSTR_6BITS),
        (REGEX_HDR_DATA_TRANSFER, REGEX_BITSTR_2BITS),
        (REGEX_HDR_COMBINED_OPCODE, REGEX_EVERYTHING),
        (REGEX_HDR_COMMAND, REGEX_EVERYTHING),
        (REGEX_HDR_REFERENCE, REGEX_EVERYTHING),
    ]

    command_set_name: str


class GeneralCommandStatusValues(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r".*(Generic|General)\s+Command\s+Status\s+Values.*"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (REGEX_HDR_VALUE, REGEX_EVERYTHING),
        (REGEX_HDR_DEFINITION, REGEX_EVERYTHING),
        (r"(Commands.Affected)", REGEX_EVERYTHING),
    ]


class CommandSpecificStatusValues(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"(?P<command_name>[\w\s]+)\s+-\s+Command\s+Specific\s+Status\s+Values"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (REGEX_HDR_VALUE, REGEX_EVERYTHING),
        (REGEX_HDR_DESCRIPTION, REGEX_EVERYTHING),
        (REGEX_HDR_COMMANDS_AFFECTED, REGEX_EVERYTHING),
    ]
    command_name: str


class FeatureIdentifiers(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*Feature\s*Identifiers.*"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (r"(Feature.Identifier)", REGEX_EVERYTHING),
        (r"(Persistent.Across.Power.Cycle.and.Reset).*", REGEX_EVERYTHING),
        (r"(Uses.Memory.Buffer.for.Attributes)", REGEX_EVERYTHING),
        (REGEX_HDR_DESCRIPTION, REGEX_EVERYTHING),
        (REGEX_HDR_SCOPE, REGEX_EVERYTHING),
    ]


class FeatureSupport(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*Feature\s*Support.*"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (r"(Feature.Name).*", REGEX_EVERYTHING),
        (r"(Feature.Support.Requirements).*", REGEX_EVERYTHING),
        (r"(Logged.in.Persistent.Event.Log).*", REGEX_EVERYTHING),
    ]


class LogPageIdentifiers(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*Log\s+Page\s+Identifiers.*"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (r"(Log.Page.Identifier).*", REGEX_EVERYTHING),
        (r"(Scope.and.Support).*", REGEX_EVERYTHING),
        (r"(Log.Page.Name).*", REGEX_EVERYTHING),
        (REGEX_HDR_REFERENCE, REGEX_EVERYTHING),
    ]


class Offset(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*offset"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (REGEX_HDR_BITS, REGEX_EVERYTHING),
        (REGEX_HDR_TYPE, REGEX_EVERYTHING),
        (REGEX_HDR_RESET, REGEX_EVERYTHING),
        (REGEX_HDR_DESCRIPTION, REGEX_EVERYTHING),
    ]


class PropertyDefinition(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*Property Definition.*"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (r"(Offset.\(OFST\)).*", REGEX_EVERYTHING),
        (r"(Size.\(in.bytes\)).*", REGEX_EVERYTHING),
        (r"(I/O Controller).*", REGEX_EVERYTHING),
        (r"(Administrative.Controller).*", REGEX_EVERYTHING),
        (r"(Discovery.Controller).*", REGEX_EVERYTHING),
        (r"(Name).*", REGEX_EVERYTHING),
    ]


def get_figure_enriching_classes():
    """
    To avoid manually crafting a list of classes, this function
    introspectively examines this module for applicable
    classes with "REGEX_FIGURE_DESCRIPTION" class attribute.
    """
    return [
        cls
        for _, cls in inspect.getmembers(senfd.documents.enriched, inspect.isclass)
        if issubclass(cls, EnrichedFigure)
        and (cls is not senfd.documents.enriched.EnrichedFigure)
        and hasattr(cls, "REGEX_FIGURE_DESCRIPTION")
    ]


class EnrichedFigureDocument(Document):

    SUFFIX_JSON: ClassVar[str] = ".enriched.figure.document.json"
    SUFFIX_HTML: ClassVar[str] = ".enriched.figure.document.html"

    FILENAME_SCHEMA: ClassVar[str] = "enriched.figure.document.schema.json"
    FILENAME_HTML_TEMPLATE: ClassVar[str] = "enriched.figure.document.html.jinja2"

    acronyms: List[Acronyms] = Field(default_factory=list)
    io_controller_command_set_support_requirements: List[
        IoControllerCommandSetSupportRequirements
    ] = Field(default_factory=list)
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

    nontabular: List[Figure] = Field(default_factory=list)
    uncategorized: List[Figure] = Field(default_factory=list)

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
    def convert(path: Path) -> Tuple[Document, List[senfd.errors.TableError]]:
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
                    obj, conv_errors = candidate.from_figure_description(figure, match)
                    errors += conv_errors
                    obj.into_document(document)
                    break

            if not match:
                document.uncategorized.append(figure)

        return document, errors
