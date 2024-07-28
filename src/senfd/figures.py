"""
Figures
=======

The following classses model the figures found in documents.
"""

import inspect
import re
from typing import ClassVar, Optional

from pydantic import BaseModel

import senfd.tables
from senfd.utils import pascal_to_snake


class Figure(BaseModel):
    """
    A figure as captioned in a table of figures in the NVMe Specification Documents.

    This is a minimally enriched figure representation. The intent is that via regular
    expressions, it should be possible to construct instances when feeding it with
    the text from a table of figures or a table that conventionally contains a figure
    caption in the first row.

    The page number is only retrievable from table of figure captions and thus optional.
    The table data is similarly represented in a form with minimal enrichment.
    """

    REGEX_TABLE_OF_FIGURES: ClassVar[str] = (
        r"^(?P<caption>Figure\s+(?P<figure_nr>\d+)\s*:"
        r"\s*(?P<description>.*?))(?P<page_nr>\d+)?$"
    )
    REGEX_TABLE_ROW: ClassVar[str] = (
        r"^(?P<caption>Figure\s+(?P<figure_nr>\d+)\s*:" r"\s*(?P<description>.*?))$"
    )
    figure_nr: int  # Figure as numbered in the specification document
    caption: str  # The entire figure caption
    description: str  # The part of figure caption without the "Fig X:" prefix

    page_nr: Optional[int] = None
    table: Optional[senfd.tables.Table] = None

    @classmethod
    def from_regex(cls, regex, text):
        match = re.match(regex, text)
        if not match:
            return None

        data = {
            "figure_nr": int(match.group("figure_nr")),
            "caption": match.group("caption").strip(),
            "description": match.group("description").strip(),
            "table": None,
            "page_nr": None,
        }
        if "page_nr" in match.groupdict():
            data["page_nr"] = int(match.group("page_nr"))

        return cls(**data)


class FromFigureDescriptionMatch(Figure):

    @classmethod
    def from_figure_description(cls, figure, match):
        shared = set(figure.dict().keys()).intersection(set(match.groupdict().keys()))
        if shared:
            raise RuntimeError(f"cls({cls.__name__}) has overlap({shared})")

        data = figure.dict()
        mdict = match.groupdict()
        if mdict:
            data.update(mdict if mdict else {})

        return cls(**data)

    def into_document(self, document):
        key = pascal_to_snake(self.__class__.__name__)
        getattr(document, key).append(self)


class Acronyms(FromFigureDescriptionMatch):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*Acronym\s+(definitions|Descriptions)"


class IoControllerCommandSetSupport(FromFigureDescriptionMatch):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r".*-\s+(?P<command_set_name>.*)Command\s+Set\s+Support"
    )
    command_set_name: str


class CnsValues(FromFigureDescriptionMatch):
    """Enrichment of a: 'Command Dword N' table"""

    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*CNS\s+Values.*"


class CommandSupportRequirements(FromFigureDescriptionMatch):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"\s*(?P<command_span>.*)\s+Command\s*Support\s*Requirements.*"
    )
    command_span: str


class CommandSqeDataPointer(FromFigureDescriptionMatch):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"(?P<command_name>[\w\s]+)\s+-\s+Data\s+Pointer"
    )
    command_name: str


class CommandSqeDwords(FromFigureDescriptionMatch):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"(?P<command_name>[\w\s]+)\s*-\s*Command\s*Dword\s*"
        r"(?P<command_dword_lower>\d+)"
        r".*and.*?\s(?P<command_dword_upper>\d+)"
    )
    command_name: str
    command_dword_lower: str
    command_dword_upper: Optional[str]


class CommandSqeDword(FromFigureDescriptionMatch):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"(?P<command_name>[\w\s]+)\s*-\s*Command\s*Dword\s*(?P<command_dword>\d+).*?"
    )
    command_name: str
    command_dword: str


class CommandCqeDword(FromFigureDescriptionMatch):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"(?P<command_name>[\w\s]+)\s+-\s+"
        r"Completion\sQueue\sEntry\sDword\s(?P<command_dword>\d+)"
    )
    command_name: str
    command_dword: str


class CommandSetOpcodes(FromFigureDescriptionMatch):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"Opcodes\sfor\s(?P<command_set_name>.*)\sCommands"
    )
    command_set_name: str


class GeneralCommandStatusValues(FromFigureDescriptionMatch):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r".*(Generic|General)\s+Command\s+Status\s+Values.*"
    )


class CommandSpecificStatusValues(FromFigureDescriptionMatch):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"(?P<command_name>[\w\s]+)\s+-\s+Command\s+Specific\s+Status\s+Values"
    )
    command_name: str


class FeatureIdentifiers(FromFigureDescriptionMatch):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*Feature\s*Identifiers.*"


class FeatureSupport(FromFigureDescriptionMatch):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*Feature\s*Support.*"


class LogPageIdentifiers(FromFigureDescriptionMatch):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*Log\s+Page\s+Identifiers.*"


class Offset(FromFigureDescriptionMatch):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*offset"


class PropertyDefinition(FromFigureDescriptionMatch):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*Property Definition.*"


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
