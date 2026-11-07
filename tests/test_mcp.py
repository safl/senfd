import asyncio
import os
import shutil
from pathlib import Path

import pytest

mcp = pytest.importorskip("mcp")

SPEC = Path("example") / "output" / "merged.spec.document.json"


def test_the_queries_are_tools_of_the_server_over_stdio():
    """As an agent runs it: senfd-mcp over stdio, asked for a command's dword"""

    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    executable = shutil.which("senfd-mcp")
    assert executable, "senfd-mcp is not installed"
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
        "search",
        "section",
        "errata",
    ]
    (content,) = result.content
    assert content.text.splitlines() == [
        "Ding: Foobar command, opcode 01h [example, 1.1, Figure 1, page 1]",
        "cdw10 [example, 1.2, Figure 2, page 2]",
        "  31:16 Reserved",
        "  15:00 Foo Count (FCNT)",
    ]


def test_a_missing_model_is_said_to_the_client(tmp_path, monkeypatch):
    import senfd.mcp_server

    monkeypatch.setenv("SENFD_SPEC", str(tmp_path / "missing.json"))
    senfd.mcp_server.spec.cache_clear()
    with pytest.raises(RuntimeError, match="No model of the specification at"):
        senfd.mcp_server.command("ding")
    senfd.mcp_server.spec.cache_clear()


def test_every_tool_answers_from_the_model(monkeypatch):
    import senfd.mcp_server

    monkeypatch.setenv("SENFD_SPEC", str(SPEC.resolve()))
    senfd.mcp_server.spec.cache_clear()
    assert senfd.mcp_server.feature("C0h").startswith("C0h Foo Config")
    assert senfd.mcp_server.log_page("C0h").startswith("C0h Foo Statistics")
    assert senfd.mcp_server.structure("FOOCAP").startswith("FOOCAP")
    assert "Ding cdw10" in senfd.mcp_server.search("FCNT")
    assert senfd.mcp_server.section("1.2").startswith("example 1.2 Ding command")
    assert "beyond the 64 bits" in senfd.mcp_server.errata("example")
    senfd.mcp_server.spec.cache_clear()
