from __future__ import annotations

from typing import Any, Dict

from mcp.server.fastmcp import FastMCP
from mcp.server.streamable_http_manager import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.mcp_service import AgentGuardMCPService

service = AgentGuardMCPService()
mcp = FastMCP(
    "agentguard-trusted-execution",
    streamable_http_path="/mcp",
    stateless_http=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    ),
)


@mcp.tool()
def preview_activity(
    title: str,
    starts_at: str,
    location: str,
    recipient: str,
    recipient_count: int,
    notice_content: str,
    source_trust: str = "MODEL_GENERATED",
) -> Dict[str, Any]:
    """Preview policy decisions only; never create tasks or execute tools."""

    return service.preview_activity(
        title,
        starts_at,
        location,
        recipient,
        recipient_count,
        notice_content,
        source_trust,
    )


@mcp.tool()
def runtime_status() -> Dict[str, Any]:
    """Return MCP runtime health, policy mode, tools and circuit states."""

    return service.runtime_status()


@mcp.custom_route("/ping", methods=["GET"])
async def ping(_request: Request) -> JSONResponse:
    return JSONResponse(service.runtime_status())


app = mcp.streamable_http_app()
