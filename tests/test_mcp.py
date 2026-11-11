# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import asyncio
import os
import shutil
from pathlib import Path

import pytest

mcp = pytest.importorskip("mcp")

SPEC = Path("example") / "output" / "merged.spec.document.json"


def test_the_queries_are_tools_of_the_server_over_stdio():
    """As an agent runs it: sate-mcp over stdio, asked for a command's dword"""

    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    executable = shutil.which("sate-mcp")
    assert executable, "sate-mcp is not installed"
    parameters = StdioServerParameters(
        command=executable, env={**os.environ, "SENFD_SPEC": str(SPEC.resolve())}
    )

    async def ask():
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                result = await session.call_tool(
                    "command", {"name": "ding", "dword": 10}
                )
                return [t.name for t in tools.tools], result

    names, result = asyncio.run(ask())
    assert names == [
        "command",
        "feature",
        "log_page",
        "structure",
        "value",
        "status",
        "search",
        "section",
        "errata",
        "lint",
    ]
    (content,) = result.content
    assert content.text.splitlines() == [
        "Ding: Foobar command, opcode 01h [example, 1.1, Figure 1, page 1]",
        "cdw10 [example, 1.2, Figure 2, page 2]",
        "  31:16 Reserved",
        "  15:00 Foo Count (FCNT)",
    ]


def test_a_missing_model_is_said_to_the_client(tmp_path, monkeypatch):
    import senfd.sate.mcp

    monkeypatch.setenv("SENFD_SPEC", str(tmp_path / "missing.json"))
    senfd.sate.mcp.loaded.cache_clear()
    with pytest.raises(RuntimeError, match="No data model of the specification at"):
        senfd.sate.mcp.command("ding")
    senfd.sate.mcp.loaded.cache_clear()


def test_every_tool_answers_from_the_model(monkeypatch):
    import senfd.sate.mcp

    monkeypatch.setenv("SENFD_SPEC", str(SPEC.resolve()))
    senfd.sate.mcp.loaded.cache_clear()
    assert senfd.sate.mcp.feature("C0h").startswith("C0h Foo Config")
    assert senfd.sate.mcp.log_page("C0h").startswith("C0h Foo Statistics")
    assert senfd.sate.mcp.structure("FOOCAP").startswith("FOOCAP")
    assert "Ding cdw10" in senfd.sate.mcp.search("FCNT")
    assert senfd.sate.mcp.value("status code 82h").startswith("82h Foo Lost")
    assert senfd.sate.mcp.section("1.2").startswith("example 1.2 Ding command")
    assert "beyond the 64 bits" in senfd.sate.mcp.errata("example")
    senfd.sate.mcp.loaded.cache_clear()
