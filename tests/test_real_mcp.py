"""E2E tests for MCP client-session capture against the real mcp SDK.

Runs a real in-memory MCP server (mcp >= 2.0 MCPServer) and a real
ClientSession, then asserts that dashcam recorded the tool traffic.
Skipped automatically when the mcp SDK is not installed.
"""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("mcp", reason="mcp SDK not installed")

from dashcam import patcher  # noqa: E402
from dashcam.storage import Store  # noqa: E402


@pytest.fixture(scope="module")
def store(tmp_path_factory, restore_real_sdks_fn):
    s = Store(str(tmp_path_factory.mktemp("realmcp") / "realmcp.db"))
    patched = patcher.instrument(s)
    assert any("call_tool" in k for k in patched), patched

    yield s

    restore_real_sdks_fn()
    s.close()


def _make_server():
    from mcp.server.mcpserver import MCPServer

    server = MCPServer("dashcam-test")

    def echo(text: str) -> str:
        return f"echo: {text}"

    server.add_tool(echo, name="echo")

    def boom() -> str:
        raise RuntimeError("tool exploded")

    server.add_tool(boom, name="boom")
    return server


async def _run_session(server, calls):
    from mcp.client.session import ClientSession
    from mcp.shared.memory import create_client_server_memory_streams

    async with create_client_server_memory_streams() as (c_streams, s_streams):
        lls = server._lowlevel_server
        server_task = asyncio.create_task(
            lls.run(s_streams[0], s_streams[1], lls.create_initialization_options())
        )
        try:
            async with ClientSession(c_streams[0], c_streams[1]) as session:
                await session.initialize()
                await calls(session)
        finally:
            server_task.cancel()
            try:
                await server_task
            except BaseException:
                pass


def _spans(store):
    out = []
    for t in store.list_traces(50):
        out.extend(store.get_trace(t["id"])["spans"])
    return out


def test_mcp_call_tool(store):
    async def calls(session):
        result = await session.call_tool("echo", {"text": "hi"})
        assert result.content[0].text == "echo: hi"

    asyncio.run(_run_session(_make_server(), calls))

    spans = [s for s in _spans(store) if s["kind"] == "call_tool"]
    assert len(spans) == 1, spans
    s = spans[0]
    assert s["provider"] == "mcp"
    assert s["model"] == "echo"
    assert s["request"] == {"name": "echo", "arguments": {"text": "hi"}}
    assert s["response"]["content"][0]["text"] == "echo: hi"
    assert s["error"] is None
    assert s["cost"] == 0


def test_mcp_list_tools(store):
    async def calls(session):
        result = await session.list_tools()
        names = {t.name for t in result.tools}
        assert names == {"echo", "boom"}

    asyncio.run(_run_session(_make_server(), calls))

    # session.initialize() also triggers a list_tools internally, so take the
    # last one recorded (the explicit call from this test).
    spans = [s for s in _spans(store) if s["kind"] == "list_tools"]
    assert spans, "no list_tools span recorded"
    s = spans[-1]
    assert s["provider"] == "mcp"
    tool_names = {t["name"] for t in s["response"]["tools"]}
    assert tool_names == {"echo", "boom"}


def test_mcp_trace_grouping(store):
    """LLM call + MCP call in one thread join the same trace."""

    async def calls(session):
        await session.call_tool("echo", {"text": "one"})
        await session.call_tool("echo", {"text": "two"})

    asyncio.run(_run_session(_make_server(), calls))

    traces = store.list_traces(50)
    mcp_traces = [t for t in traces if t["span_count"] >= 2]
    assert mcp_traces, traces
    assert mcp_traces[0]["name"] == "mcp: echo"
