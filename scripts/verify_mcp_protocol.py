"""Exercise the deployed read-only MCP surface with the pinned SDK.

Run after starting the container locally:
    python scripts/verify_mcp_protocol.py

This sends only fictional activity data to the loopback MCP server.
"""

from __future__ import annotations

import asyncio
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

URL = "http://127.0.0.1:8080/mcp"
TOOLS = {"preview_activity", "explain_policy", "runtime_status"}


def tool_data(result):  # type: ignore[no-untyped-def]
    if result.isError:
        raise AssertionError("MCP tool reported an error")
    if result.structuredContent:
        return result.structuredContent
    for item in result.content:
        if item.type == "text":
            value = json.loads(item.text)
            if isinstance(value, dict):
                return value
    raise AssertionError("MCP tool returned no object")


async def main() -> None:
    async with streamable_http_client(URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            names = {tool.name for tool in listed.tools}
            assert names == TOOLS, f"unexpected MCP tools: {sorted(names)}"

            status = tool_data(await session.call_tool("runtime_status", {}))
            assert status["policy_mode"] == "deterministic"
            assert set(status["registered_tools"]) == TOOLS

            guidance = tool_data(
                await session.call_tool(
                    "explain_policy", {"reason_code": "RECIPIENT_DOMAIN_DENIED"}
                )
            )
            assert guidance["mode"] == "READ_ONLY_GUIDANCE"
            assert len(guidance["policy_sha256"]) == 64

            preview = tool_data(
                await session.call_tool(
                    "preview_activity",
                    {
                        "title": "虚构社区读书会",
                        "starts_at": "2026-12-01T09:00:00+08:00",
                        "location": "社区图书馆",
                        "recipient": "readers@example.org",
                        "recipient_count": 20,
                        "notice_content": "请提前到场",
                        "source_trust": "USER_CONFIRMED",
                        "update_shared_file": False,
                    },
                )
            )
            assert preview["mode"] == "PREVIEW_ONLY"
            assert [step["tool_name"] for step in preview["steps"]] == [
                "calendar", "send_notice"
            ]
            assert all(
                step["decision"] in {"ALLOW", "CONFIRM", "BLOCK"}
                for step in preview["steps"]
            )
            print("MCP protocol OK: three read-only tools, guidance and preview")


if __name__ == "__main__":
    asyncio.run(main())
