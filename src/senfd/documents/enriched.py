import inspect
import re
from pathlib import Path
from typing import ClassVar, List, Optional, Tuple

from pydantic import Field

import senfd.models
import senfd.schemas
import senfd.tables
from senfd.documents.base import (
    TRANSLATION_TABLE,
    Converter,
    Document,
    strip_all_suffixes,
)
from senfd.documents.plain import Figure, FigureDocument
from senfd.errors import Error
from senfd.utils import pascal_to_snake

REGEX_WILDCARD = r"(?P<wildcard>.*)"

REGEX_VAL_BITRANGE = r"(?:(?P<upper>\d{1,2}):)?(?P<lower>\d{1,2})"
REGEX_VAL_BITSTR_2BITS = r"(?P<bitstr_2bits>\d{2}b)"
REGEX_VAL_BITSTR_6BITS = r"(?P<bitstr_6bits>\d{4}\s\d{2}b)"
REGEX_VAL_BYTES_HEX = r"(?P<hex>[a-zA-Z0-9]{2}h)"
REGEX_VAL_COMMAND_NAME = r"^(?P<command_name>[a-zA-Z -/]*)[ \d]*$"
REGEX_VAL_COMMANDS_AFFECTED = r"(?P<commands_affected>.*)"
REGEX_VAL_DEFINIITON = r"(?P<definition>.*)"
REGEX_VAL_DESCRIPTION = r"(?P<description>.*)"
REGEX_VAL_FIELD = (
    r"(?P<name>[ \w]+)"
    r"("
    r"\((?P<acronym>[^\)]+)\)"
    r")?"
    r"(:\s*(?P<description>.*))?"
)
REGEX_VAL_REFER_TO_BASESPEC = (
    r"(?P<reference>Refer.to.the.NVM.Express.Base.Specification).*"
)
REGEX_VAL_REFERENCE = r"(?P<section>.*)"
REGEX_VAL_SUPPORT_REQUIREMENT = r"(?P<requirement>O|M|P)"
REGEX_VAL_TERM = r"(?P<term>.*)"
REGEX_VAL_YESNO = r"(?P<yn>NOTE|Note|Yes|No|Y|N)[ \d]*?"

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

    def into_document(self, document):
        key = pascal_to_snake(self.__class__.__name__)
        getattr(document, key).append(self)


class Acronyms(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*Acronym\s+(definitions|Descriptions)"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (REGEX_HDR_ACRONYM, REGEX_VAL_TERM),
        (REGEX_HDR_DEFINITION, REGEX_WILDCARD),
    ]


class IoControllerCommandSetSupportRequirements(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r".*-\s+(?P<command_set_name>.*)Command\s+Set\s+Support"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (REGEX_HDR_COMMAND, REGEX_VAL_COMMAND_NAME),
        (r"^(Command\sSupport\sRequirements)[ \d]*?$", REGEX_VAL_SUPPORT_REQUIREMENT),
    ]

    command_set_name: str


class CommandSupportRequirements(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"\s*(?P<command_span>.*)\s+Command\s*Support\s*Requirements.*"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (REGEX_HDR_COMMAND, REGEX_VAL_COMMAND_NAME),
        (r"(Command\sSupport\sRequirements)\s\d", REGEX_VAL_SUPPORT_REQUIREMENT),
    ]

    command_span: str


class CnsValues(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*CNS\s+Values.*"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (r"(CNS.Value)", REGEX_VAL_BYTES_HEX),
        (r"(O\/M).*", REGEX_VAL_SUPPORT_REQUIREMENT),
        (REGEX_HDR_DEFINITION, REGEX_WILDCARD),
        (r"(NSID).*", REGEX_VAL_YESNO.replace("yn", "nsid")),
        (r"(CNTID).*", REGEX_VAL_YESNO.replace("yn", "cntid")),
        (r"(CSI).*", REGEX_VAL_YESNO.replace("yn", "csi")),
        (REGEX_HDR_REFERENCE, REGEX_VAL_REFERENCE),
    ]


class CommandSqeDataPointer(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"(?P<command_name>[\w\s]+)\s+-\s+Data\s+Pointer"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (REGEX_HDR_BITS, REGEX_VAL_BITRANGE),
        (REGEX_HDR_DESCRIPTION, REGEX_WILDCARD),
    ]

    command_name: str


class CommandSqeDwords(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"(?P<command_name>[\w\s]+)\s*-\s*Command\s*Dword\s*"
        r"(?P<command_dword_lower>\d+)"
        r".*and.*?\s(?P<command_dword_upper>\d+)$"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (REGEX_HDR_BITS, REGEX_VAL_BITRANGE),
        (REGEX_HDR_DESCRIPTION, REGEX_VAL_FIELD),
    ]

    command_name: str
    command_dword_lower: int
    command_dword_upper: int


class CommandSqeDword(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"^(?P<command_name>[\w\s]+)\s+-\s+Command\s*Dword\s*(?P<command_dword>\d+)$"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (REGEX_HDR_BITS, REGEX_VAL_BITRANGE),
        (REGEX_HDR_DESCRIPTION, REGEX_VAL_FIELD),
    ]

    command_name: str
    command_dword: int


class CommandCqeDword(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"(?P<command_name>[\w\s]+)\s+-\s+"
        r"Completion\sQueue\sEntry\sDword\s(?P<command_dword>\d+)"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (REGEX_HDR_BITS, REGEX_VAL_BITRANGE),
        (REGEX_HDR_DESCRIPTION, REGEX_VAL_FIELD),
    ]

    command_name: str
    command_dword: str


class CommandAdminOpcodes(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r"Opcodes.for.Admin.Commands"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (REGEX_HDR_FUNCTION, REGEX_VAL_BITSTR_6BITS),
        (REGEX_HDR_DATA_TRANSFER, REGEX_VAL_BITSTR_2BITS),
        (REGEX_HDR_COMBINED_OPCODE, REGEX_VAL_BYTES_HEX),
        (r"(Namespace.Identifier.Used).*", REGEX_VAL_YESNO.replace("yn", "nsid_used")),
        (REGEX_HDR_COMMAND, REGEX_VAL_COMMAND_NAME),
        (REGEX_HDR_REFERENCE, REGEX_VAL_REFERENCE),
    ]


class CommandIoOpcodes(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r"Opcodes.for.I.O.Commands"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (REGEX_HDR_FUNCTION, REGEX_VAL_BITSTR_6BITS),
        (REGEX_HDR_DATA_TRANSFER, REGEX_VAL_BITSTR_2BITS),
        (REGEX_HDR_COMBINED_OPCODE, REGEX_VAL_BYTES_HEX),
        (REGEX_HDR_COMMAND, REGEX_VAL_COMMAND_NAME),
        (REGEX_HDR_REFERENCE, REGEX_VAL_REFERENCE),
        (REGEX_HDR_REFERENCE, REGEX_WILDCARD),
    ]


class CommandSetOpcodes(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"Opcodes\sfor\s(?P<command_set_name>.*)\sCommands"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (REGEX_HDR_FUNCTION, REGEX_VAL_BITSTR_6BITS),
        (REGEX_HDR_DATA_TRANSFER, REGEX_VAL_BITSTR_2BITS),
        (REGEX_HDR_COMBINED_OPCODE, REGEX_VAL_BYTES_HEX),
        (REGEX_HDR_COMMAND, REGEX_VAL_COMMAND_NAME),
        (REGEX_HDR_REFERENCE, REGEX_WILDCARD),
    ]

    command_set_name: str


class GeneralCommandStatusValues(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r".*(Generic|General)\s+Command\s+Status\s+Values.*"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (REGEX_HDR_VALUE, REGEX_WILDCARD),
        (REGEX_HDR_DEFINITION, REGEX_WILDCARD),
        (r"(Commands.Affected)", REGEX_WILDCARD),
    ]


class CommandSpecificStatusValues(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"(?P<command_name>[\w\s]+)\s+-\s+Command\s+Specific\s+Status\s+Values"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (REGEX_HDR_VALUE, REGEX_VAL_BYTES_HEX),
        (REGEX_HDR_DESCRIPTION, REGEX_VAL_DESCRIPTION),
        (REGEX_HDR_COMMANDS_AFFECTED, REGEX_VAL_COMMANDS_AFFECTED),
    ]
    command_name: str


class FeatureIdentifiers(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*Feature\s*Identifiers.*"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (r"(Feature.Identifier)", REGEX_WILDCARD),
        (r"(Persistent.Across.Power.Cycle.and.Reset).*", REGEX_WILDCARD),
        (r"(Uses.Memory.Buffer.for.Attributes)", REGEX_WILDCARD),
        (REGEX_HDR_DESCRIPTION, REGEX_WILDCARD),
        (REGEX_HDR_SCOPE, REGEX_WILDCARD),
    ]


class FeatureSupport(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*Feature\s*Support.*"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (r"(Feature.Name).*", REGEX_WILDCARD),
        (r"(Feature.Support.Requirements).*", REGEX_WILDCARD),
        (r"(Logged.in.Persistent.Event.Log).*", REGEX_WILDCARD),
    ]


class LogPageIdentifiers(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*Log\s+Page\s+Identifiers.*"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (r"(Log.Page.Identifier).*", REGEX_WILDCARD),
        (r"(Scope.and.Support).*", REGEX_WILDCARD),
        (r"(Log.Page.Name).*", REGEX_WILDCARD),
        (REGEX_HDR_REFERENCE, REGEX_WILDCARD),
    ]


class Offset(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*offset"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (REGEX_HDR_BITS, REGEX_WILDCARD),
        (REGEX_HDR_TYPE, REGEX_WILDCARD),
        (REGEX_HDR_RESET, REGEX_WILDCARD),
        (REGEX_HDR_DESCRIPTION, REGEX_WILDCARD),
    ]


class PropertyDefinition(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*Property Definition.*"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (r"(Offset.\(OFST\)).*", REGEX_WILDCARD),
        (r"(Size.\(in.bytes\)).*", REGEX_WILDCARD),
        (r"(I/O Controller).*", REGEX_WILDCARD),
        (r"(Administrative.Controller).*", REGEX_WILDCARD),
        (r"(Discovery.Controller).*", REGEX_WILDCARD),
        (r"(Name).*", REGEX_WILDCARD),
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
    command_admin_opcodes: List[CommandAdminOpcodes] = Field(default_factory=list)
    command_io_opcodes: List[CommandIoOpcodes] = Field(default_factory=list)
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


class FromFigureDocument(Converter):
    """
    Constructs an EnrichedDocument from a given PlainDocument

    Figures are enriched by extraction, type coercion, and conversion of using data from
    the figure description and table content.
    """

    @staticmethod
    def is_applicable(path: Path) -> bool:
        return "".join(path.suffixes).lower() == ".plain.figure.document.json"

    @staticmethod
    def check_regex(figure, match) -> List[senfd.errors.Error]:

        shared = set(figure.model_dump().keys()).intersection(
            set(match.groupdict().keys())
        )
        if shared:
            return [
                senfd.errors.ImplementationError(
                    message=f"cls({figure.__class__.__name__}) has overlap({shared})"
                )
            ]

        return []

    @staticmethod
    def check_table_data(
        figure: EnrichedFigure,
    ) -> Tuple[Optional[senfd.errors.Error], List[senfd.errors.Error]]:
        """Check for blocking errors, for which enrichment cannot continue"""

        if figure.table is None:
            return (
                senfd.errors.FigureTableMissingError(
                    figure_nr=figure.figure_nr, message="Missing table"
                ),
                [],
            )
        if len(figure.table.rows) < 2:
            return (
                senfd.errors.FigureTableMissingRowsError(
                    figure_nr=figure.figure_nr, message=r"Number of rows < 2"
                ),
                [],
            )
        if not hasattr(figure, "REGEX_GRID"):
            return (
                senfd.errors.FigureRegexGridMissingError(
                    figure_nr=figure.figure_nr, message="Missing REGEX_GRID"
                ),
                [],
            )

        lengths = list(set([len(row.cells) for row in figure.table.rows]))
        if len(lengths) != 1:
            return None, [
                senfd.errors.IrregularTableError(
                    figure_nr=figure.figure_nr,
                    message=f"Varying row lengths({lengths})",
                    lengths=lengths,
                )
            ]

        return None, []

    @staticmethod
    def check_grid(figure: EnrichedFigure) -> List[senfd.errors.Error]:
        """
        Checks the state of the grid, assuming state after enrichment, thus expecting
        the grid to contain headers, fields, and value. Returning error(s) if it does
        not.
        """

        errors: List[senfd.errors.Error] = []

        if not figure.grid.headers:
            errors.append(
                senfd.errors.FigureNoGridHeaders(
                    figure_nr=figure.figure_nr,
                    message=(
                        "Grid is missing headers;"
                        f" check {figure.__class__.__name__}.REGEX_GRID"
                    ),
                )
            )

        if not figure.grid.fields:
            errors.append(
                senfd.errors.FigureNoGridHeaders(
                    figure_nr=figure.figure_nr,
                    message=(
                        "Grid is missing fields;"
                        f" check {figure.__class__.__name__}.REGEX_GRID"
                    ),
                )
            )

        if not figure.grid.values:
            errors.append(
                senfd.errors.FigureNoGridValues(
                    figure_nr=figure.figure_nr,
                    message=(
                        "Grid is missing values;"
                        f" check {figure.__class__.__name__}.REGEX_GRID"
                    ),
                )
            )

        return errors

    @staticmethod
    def enrich(cls, figure: Figure, match) -> Tuple[Optional[Figure], List[Error]]:
        """Returns an EnrichedFigure from the givven Figure"""

        errors: List[senfd.errors.Error] = []

        # Merge figure data with fields from regex
        data = figure.model_dump()
        mdict = match.groupdict()
        if mdict:
            data.update(mdict if mdict else {})
        enriched = cls(**data)

        # Check for non-blocking error-conditions
        errors += FromFigureDocument.check_regex(enriched, match)
        error, non_blocking = FromFigureDocument.check_table_data(enriched)
        errors += non_blocking
        if error:
            errors.append(error)
            return None, errors

        regex_hdr, regex_val = zip(*enriched.REGEX_GRID)

        header_names: List[str] = []

        fields: List[str] = []
        values: List[List[str | int]] = []
        for row_idx, row in enumerate(enriched.table.rows[1:], 1):
            if not header_names:
                header_matches = [
                    match.group(1) if match else match
                    for match in (
                        re.match(regex, cell.text.strip().replace("\n", " "))
                        for cell, regex in zip(row.cells, regex_hdr)
                    )
                ]
                if all(header_matches):
                    header_names = [str(hdr) for hdr in header_matches]
                else:
                    errors.append(
                        senfd.errors.FigureTableRowError(
                            figure_nr=enriched.figure_nr,
                            table_nr=enriched.table.table_nr,
                            row_idx=row_idx,
                            message="Did not match REGEX_GRID/Headers",
                        )
                    )
                continue

            combined = {}
            value_errors = []
            for cell_idx, (cell, regex) in enumerate(zip(row.cells, regex_val)):

                text = cell.text.strip()
                match = re.match(regex, text)
                if match:
                    combined.update(match.groupdict())
                    continue

                value_errors.append(
                    senfd.errors.FigureTableRowCellError(
                        figure_nr=enriched.figure_nr,
                        table_nr=enriched.table.table_nr,
                        row_idx=row_idx,
                        cell_idx=cell_idx,
                        message=f"cell.text({text}) no match({regex})",
                    )
                )

            if value_errors:
                errors += value_errors
                continue

            cur_fields = list(combined.keys())
            if not fields:
                fields = cur_fields

            diff = list(set(cur_fields).difference(set(fields)))
            if diff:
                errors.append(
                    senfd.errors.FigureTableRowError(
                        figure_nr=enriched.figure_nr,
                        table_nr=enriched.table.table_nr,
                        row_idx=row_idx,
                        message=f"Unexpected fields ({fields}) != ({cur_fields})",
                    )
                )
                continue

            values.append(list(combined.values()))

        data = enriched.table.dict()
        data["headers"] = header_names
        data["fields"] = fields
        data["values"] = values

        enriched.grid = senfd.tables.Grid(**data)

        errors += FromFigureDocument.check_grid(enriched)

        return enriched, errors

    @staticmethod
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

    @staticmethod
    def convert(path: Path) -> Tuple[Document, List[Error]]:
        """Instantiate an 'organized' Document from a 'figure' document"""

        errors = []

        figure_document = FigureDocument.model_validate_json(path.read_text())

        document = EnrichedFigureDocument()
        document.meta.stem = strip_all_suffixes(path.stem)

        figure_organizers = FromFigureDocument.get_figure_enriching_classes()
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
                    enriched, conv_errors = FromFigureDocument.enrich(
                        candidate, figure, match
                    )
                    errors += conv_errors
                    if not enriched:
                        break
                    enriched.into_document(document)
                    break

            if not match:
                document.uncategorized.append(figure)

        return document, errors
