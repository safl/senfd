# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
The queries of senfd.query as the tools of an MCP server, over stdio

An agent, such as Claude Code, then answers a question about the specification
with a tool call costing a few lines, rather than by reading the documents:

    senfd *.docx --output ~/.cache/senfd
    claude mcp add sate -- sate-mcp
"""

import inspect
from functools import lru_cache
from pathlib import Path
from typing import Callable, List, Optional

from mcp.server.mcpserver import MCPServer

import senfd
import senfd.query
from senfd.documents.spec import linked
from senfd.documents.spec import SpecDocument

INSTRUCTIONS = (
    "Answers questions about the NVMe specifications from the data model senfd made of "
    "them: commands and their dwords, features and log pages by identifier, "
    "data structures and registers, and fields by acronym. Each answer cites "
    "the document and figure it came from. Use it before reading the documents."
)

server = MCPServer(name="sate", instructions=INSTRUCTIONS, version=senfd.__version__)


def tool(function: Callable[..., str]) -> Callable[..., str]:
    """A tool of the server, described by its docstring without the docstring's
    indentation, which a client would show"""

    description = inspect.cleandoc(function.__doc__ or "")
    return server.tool(structured_output=False, description=description)(function)


# The data model that sate-web gives the tools, or None, in which case the
# tools load the data model from its default path
given: Optional[SpecDocument] = None


def answer_from(document: SpecDocument) -> None:
    """Make the tools answer from 'document' instead of loading a data
    model. sate-web calls this with the data model it already holds."""

    global given
    given = document


def spec() -> SpecDocument:
    return given if given is not None else loaded()


@lru_cache(maxsize=1)
def loaded(path: Optional[Path] = None) -> SpecDocument:
    path = path or senfd.query.default_spec_path()
    try:
        return senfd.query.load(path)
    except FileNotFoundError:
        raise RuntimeError(
            f"No data model of the specification at {path}; make it with "
            f"'senfd <documents.docx> --output {path.parent}', or point "
            "SENFD_SPEC at one"
        ) from None


@tool
def command(name: str, dword: Optional[int] = None, verbose: bool = False) -> str:
    """A command's opcode and its submission queue dwords with their fields,
    and completion queue dwords; 'dword' gives one dword only, as 12 for CDW12"""

    return "\n".join(linked(spec(), senfd.query.command(spec(), name, dword, verbose)))


@tool
def feature(key: str, verbose: bool = False) -> str:
    """A feature by its identifier, as "07h", or name, with its dwords"""

    return "\n".join(linked(spec(), senfd.query.feature(spec(), key, verbose)))


@tool
def log_page(key: str, verbose: bool = False) -> str:
    """A log page by its identifier, as "02h", or name, with its structure"""

    return "\n".join(linked(spec(), senfd.query.log_page(spec(), key, verbose)))


@tool
def structure(name: str, verbose: bool = False) -> str:
    """A data structure or register by name, with its fields"""

    return "\n".join(linked(spec(), senfd.query.structure(spec(), name, verbose)))


@tool
def value(text: str, verbose: bool = False) -> str:
    """An entry of a table of values by the kind of table, the value and words
    of the entry's name, as "status code 82h", "status code type 1h", "CNS 05h"
    or "status code zone boundary error"; with 'verbose', its description and
    other columns too"""

    return "\n".join(linked(spec(), senfd.query.value(spec(), text, verbose)))


@tool
def search(text: str) -> str:
    """Fields by acronym or name, and commands, features, log pages and
    structures by name, each with where it is"""

    return "\n".join(linked(spec(), senfd.query.search(spec(), text)))


@tool
def section(key: str) -> str:
    """What a section of the specification describes, by its number, as
    "5.1.25", with its subsections, or by a word of its title"""

    return "\n".join(linked(spec(), senfd.query.section(spec(), key)))


@tool
def errata(document: str = "") -> str:
    """Candidate errata of the documents, values that are not what their kind
    must be, each with where it is; 'document' as "Base" or "NVM" narrows them"""

    return "\n".join(linked(spec(), senfd.query.errata(spec(), document)))


@tool
def lint(document: str = "") -> str:
    """What reading the figures as data found: candidate errata for the
    authors, figures of no shape senfd models, worked examples, and dwords no
    command claims; 'document' as "Base" or "NVM" narrows them"""

    return "\n".join(linked(spec(), senfd.query.lint(spec(), document)))


def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    argparse.ArgumentParser(
        description="An MCP server, over stdio, answering questions about the NVMe "
        "specifications from senfd's data model; register it with an agent, as "
        "'claude mcp add sate -- sate-mcp'"
    ).parse_args(argv)
    server.run("stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
