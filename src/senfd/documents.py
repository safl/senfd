"""
Documents
=========

The following classes model documents at different stages of parsing / processing an
NVMe specification document from a raw extract into something semantically rich.

"""

import importlib.resources as pkg_resources
import inspect
import json
import re
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional

from jinja2 import Environment, PackageLoader, select_autoescape
from pydantic import BaseModel, Field, ValidationError

import senfd.figures
import senfd.schemas
import senfd.tables

TRANSLATION_TABLE: Dict[int, str] = str.maketrans(
    {
        "–": "-",  # en dash
        "—": "-",  # em dash
        "‘": "'",  # left single quotation mark
        "’": "'",  # right single quotation mark
        "“": '"',  # left double quotation mark
        "”": '"',  # right double quotation mark
        "…": "...",  # ellipsis
        "é": "e",  # e with acute accent
        "á": "a",  # a with acute accent
        "í": "i",  # i with acute accent
        "ó": "o",  # o with acute accent
        "ú": "u",  # u with acute accent
        "ü": "u",  # u with diaeresis
        "ñ": "n",  # n with tilde
        "ç": "c",  # c with cedilla
    }
)


class DocumentMeta(BaseModel):
    version: str = senfd.__version__
    stem: str = Field(default_factory=str)


def to_file(content: str, filename: str, path: Optional[Path] = None):
    if path is None:
        path = Path.cwd() / filename
    if path.is_dir():
        path = path / filename

    path.write_text(content)


class Document(BaseModel):
    """
    Base document - providing functionality for describing and persisting documents

    The intent here is that all Documents should be representable as JSON and HTML
    """

    SUFFIX_JSON: ClassVar[str] = ".document.json"
    SUFFIX_HTML: ClassVar[str] = ".document.html"

    FILENAME_SCHEMA: ClassVar[str] = "document.schema.json"
    FILENAME_HTML_TEMPLATE: ClassVar[str] = "document.html.jinja2"

    meta: DocumentMeta = Field(default_factory=DocumentMeta)

    @classmethod
    def schema_filename(cls) -> str:
        return cls.FILENAME_SCHEMA

    @classmethod
    def to_schema_file(cls, path: Optional[Path] = None):
        """Writes the document JSON schema to file at the given 'path'"""

        to_file(
            json.dumps(cls.schema(), indent=4),
            cls.schema_filename(),
            path,
        )

    @classmethod
    def schema_static(cls) -> Dict[str, Any]:
        """Returns the content of the associated JSON schema-file"""

        with pkg_resources.open_text(senfd.schemas, cls.FILENAME_SCHEMA) as content:
            return json.load(content)

    def json_filename(self) -> str:
        return f"{self.meta.stem}{self.SUFFIX_JSON}"

    def to_json(self) -> str:
        """Returns the document as a JSON-formated string"""

        return self.model_dump_json(indent=4)

    def to_json_file(self, path: Optional[Path] = None):
        """Writes the document, formated as JSON, to file at the given 'path'"""

        to_file(self.to_json(), self.json_filename(), path)

    def html_filename(self) -> str:
        return f"{self.meta.stem}{self.SUFFIX_HTML}"

    def to_html(self) -> str:
        """Returns the document as a HTML-formatted string"""

        env = Environment(
            loader=PackageLoader("senfd", "templates"),
            autoescape=select_autoescape(["html", "xml"]),
        )
        template = env.get_template(self.FILENAME_HTML_TEMPLATE)

        return template.render(document=self)

    def to_html_file(self, path: Optional[Path] = None):
        """Writes the document to HTML-formatted file"""

        to_file(self.to_html(), self.html_filename(), path)

    def is_valid(self) -> bool:
        """Returns True when validator raises no exceptions, False otherwise"""

        try:
            self.validate(self.dict())
        except ValidationError as e:
            print(e)
            return False

        return True


class FigureDocument(Document):

    SUFFIX_JSON: ClassVar[str] = ".figure.document.json"
    SUFFIX_HTML: ClassVar[str] = ".figure.document.html"

    FILENAME_SCHEMA: ClassVar[str] = "figure.document.schema.json"
    FILENAME_HTML_TEMPLATE: ClassVar[str] = "figure.document.html.jinja2"

    figures: List[senfd.figures.Figure] = Field(default_factory=list)


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

        def get_figure_enriching_classes():
            """
            To avoid manually crafting a list of classes, this function
            introspectively examines this module for applicable
            classes with "REGEX_FIGURE_DESCRIPTION" class attribute.
            """
            return [
                cls
                for _, cls in inspect.getmembers(senfd.figures, inspect.isclass)
                if issubclass(cls, senfd.figures.FromFigureDescriptionMatch)
                and hasattr(cls, "REGEX_FIGURE_DESCRIPTION")
            ]

        figure_document = senfd.documents.FigureDocument.parse_file(path)

        document = cls()

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

        return document
