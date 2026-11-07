"""
The queries of senfd.query as the tools of an MCP server, over stdio

An agent, such as Claude Code, then answers a question about the specification
with a tool call costing a few lines, rather than by reading the documents:

    senfd *.docx --output ~/.cache/senfd
    claude mcp add senfd -- senfd-mcp
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from mcp.server.mcpserver import MCPServer

import senfd
import senfd.query
from senfd.documents.spec import SpecDocument

INSTRUCTIONS = (
    "Answers questions about the NVMe specifications from a model senfd made of "
    "them: commands and their dwords, features and log pages by identifier, "
    "data structures and registers, and fields by acronym. Each answer cites "
    "the document and figure it came from. Use it before reading the documents."
)

server = MCPServer(name="senfd", instructions=INSTRUCTIONS, version=senfd.__version__)


@lru_cache(maxsize=1)
def spec(path: Optional[Path] = None) -> SpecDocument:
    path = path or senfd.query.default_spec_path()
    try:
        return senfd.query.load(path)
    except FileNotFoundError:
        raise RuntimeError(
            f"No model of the specification at {path}; make it with "
            f"'senfd <documents.docx> --output {path.parent}', or point "
            "SENFD_SPEC at one"
        ) from None


@server.tool(structured_output=False)
def command(name: str, dword: Optional[int] = None, verbose: bool = False) -> str:
    """A command's opcode and its submission queue dwords with their fields,
    and completion queue dwords; 'dword' gives one dword only, as 12 for CDW12"""

    return "\n".join(senfd.query.command(spec(), name, dword, verbose))


@server.tool(structured_output=False)
def feature(key: str, verbose: bool = False) -> str:
    """A feature by its identifier, as "07h", or name, with its dwords"""

    return "\n".join(senfd.query.feature(spec(), key, verbose))


@server.tool(structured_output=False)
def log_page(key: str, verbose: bool = False) -> str:
    """A log page by its identifier, as "02h", or name, with its structure"""

    return "\n".join(senfd.query.log_page(spec(), key, verbose))


@server.tool(structured_output=False)
def structure(name: str, verbose: bool = False) -> str:
    """A data structure or register by name, with its fields"""

    return "\n".join(senfd.query.structure(spec(), name, verbose))


@server.tool(structured_output=False)
def search(text: str) -> str:
    """Fields by acronym or name, and commands, features, log pages and
    structures by name, each with where it is"""

    return "\n".join(senfd.query.search(spec(), text))


@server.tool(structured_output=False)
def section(key: str) -> str:
    """What a section of the specification describes, by its number, as
    "5.1.25", with its subsections, or by a word of its title"""

    return "\n".join(senfd.query.section(spec(), key))


@server.tool(structured_output=False)
def errata(document: str = "") -> str:
    """Candidate errata of the documents, values that are not what their kind
    must be, each with where it is; 'document' as "Base" or "NVM" narrows them"""

    return "\n".join(senfd.query.errata(spec(), document))


def main() -> int:
    server.run("stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
