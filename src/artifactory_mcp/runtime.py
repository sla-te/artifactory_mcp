from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from .settings import SETTINGS

logging.basicConfig(
    level=getattr(logging, SETTINGS.mcp_log_level),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("artifactory_mcp")


def _build_transport_security_settings() -> TransportSecuritySettings:
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=SETTINGS.mcp_enable_dns_rebinding_protection,
        allowed_hosts=SETTINGS.mcp_allowed_hosts,
        allowed_origins=SETTINGS.mcp_allowed_origins,
    )


mcp = FastMCP(
    name="artifactory-mcp",
    instructions=(
        "MCP server for JFrog Artifactory using dohq-artifactory. "
        "Supports convenience artifact tools plus generic root/path/handle method invocation "
        "to cover full underlying client functionality."
    ),
    host=SETTINGS.mcp_host,
    port=SETTINGS.mcp_port,
    streamable_http_path=SETTINGS.mcp_streamable_http_path,
    stateless_http=SETTINGS.mcp_stateless_http,
    json_response=SETTINGS.mcp_json_response,
    transport_security=_build_transport_security_settings(),
    log_level=SETTINGS.mcp_log_level,
)
