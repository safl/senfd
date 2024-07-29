import re
from pathlib import Path
from typing import ClassVar, List

from pydantic import Field

import senfd.figures
import senfd.schemas
import senfd.tables
from senfd.documents.base import (
    TRANSLATION_TABLE,
    Converter,
    Document,
    DocumentMeta,
    strip_all_suffixes,
)
from senfd.documents.figure import FigureDocument
from senfd.figures import get_figure_enriching_classes


class CategorizedFigureDocumentMeta(DocumentMeta):
    tabular: List[int] = Field(default_factory=list)
    nontabular: List[senfd.figures.Figure] = Field(default_factory=list)
    uncategorized: List[senfd.figures.Figure] = Field(default_factory=list)


class CategorizedFigureDocument(Document):

    SUFFIX_JSON: ClassVar[str] = ".categorized.figure.document.json"
    SUFFIX_HTML: ClassVar[str] = ".categorized.figure.document.html"

    FILENAME_SCHEMA: ClassVar[str] = "categorized.figure.document.schema.json"
    FILENAME_HTML_TEMPLATE: ClassVar[str] = "categorized.figure.document.html.jinja2"

    meta: CategorizedFigureDocumentMeta = Field(
        default_factory=CategorizedFigureDocumentMeta
    )
    acronyms: List[senfd.figures.Acronyms] = Field(default_factory=list)
    io_controller_command_set_support: List[
        senfd.figures.IoControllerCommandSetSupport
    ] = Field(default_factory=list)
    command_set_opcodes: List[senfd.figures.CommandSetOpcodes] = Field(
        default_factory=list
    )
    command_support_requirements: List[senfd.figures.CommandSupportRequirements] = (
        Field(default_factory=list)
    )
    command_sqe_dword: List[senfd.figures.CommandSqeDword] = Field(default_factory=list)
    command_sqe_dwords: List[senfd.figures.CommandSqeDwords] = Field(
        default_factory=list
    )
    command_sqe_data_pointer: List[senfd.figures.CommandSqeDataPointer] = Field(
        default_factory=list
    )
    command_cqe_dword: List[senfd.figures.CommandCqeDword] = Field(default_factory=list)
    command_specific_status_values: List[senfd.figures.CommandSpecificStatusValues] = (
        Field(default_factory=list)
    )
    general_command_status_values: List[senfd.figures.GeneralCommandStatusValues] = (
        Field(default_factory=list)
    )
    cns_values: List[senfd.figures.CnsValues] = Field(default_factory=list)
    feature_support: List[senfd.figures.FeatureSupport] = Field(default_factory=list)
    feature_identifiers: List[senfd.figures.FeatureIdentifiers] = Field(
        default_factory=list
    )
    log_page_identifiers: List[senfd.figures.LogPageIdentifiers] = Field(
        default_factory=list
    )
    offset: List[senfd.figures.Offset] = Field(default_factory=list)
    property_definition: List[senfd.figures.PropertyDefinition] = Field(
        default_factory=list
    )

    @classmethod
    def from_figure_document_file(cls, path: Path):
        """Instantiate an 'organized' Document from a 'figure' document"""

        document, errors = FromFigureDocument.convert(path)
        return document


class FromFigureDocument(Converter):

    @staticmethod
    def is_applicable(path: Path) -> bool:
        return "".join(path.suffixes).lower() == ".figure.document.json"

    @staticmethod
    def convert(path: Path):
        """Instantiate an 'organized' Document from a 'figure' document"""

        figure_document = FigureDocument.parse_file(path)

        document = CategorizedFigureDocument()
        document.meta.stem = strip_all_suffixes(path.stem)

        figure_organizers = get_figure_enriching_classes()
        for figure in figure_document.figures:
            if not figure.table:
                document.meta.nontabular.append(figure)
                continue

            match = None
            description = figure.description.translate(TRANSLATION_TABLE)
            for candidate in figure_organizers:
                match = re.match(
                    candidate.REGEX_FIGURE_DESCRIPTION, description, flags=re.IGNORECASE
                )
                if match:
                    obj = candidate.from_figure_description(figure, match)
                    obj.into_document(document)
                    document.meta.tabular.append(obj.figure_nr)
                    break

            if not match:
                document.meta.uncategorized.append(figure)

        return document, {}
