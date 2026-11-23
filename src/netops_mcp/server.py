"""Servidor MCP de netops-mcp: herramientas de redes para Claude."""

import ipaddress
from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

mcp = MCPServer(name="netops-mcp")


@mcp.tool()
def calcular_subred(
    red: Annotated[str, Field(description="Red en CIDR, p. ej. 192.168.1.0/24")],
) -> dict:
    """Calcula red, máscara, wildcard, broadcast y rango de hosts de una red IPv4."""
    try:
        net = ipaddress.IPv4Network(red, strict=False)
    except ValueError:
        raise ToolError(
            f"'{red}' no es una red IPv4 válida. Usa formato CIDR, ej. 192.168.1.0/24."
        ) from None

    return {
        "red": str(net.network_address),
        "mascara": str(net.netmask),
        "wildcard": str(net.hostmask),
        "broadcast": str(net.broadcast_address),
        "primer_host": str(net.network_address + 1),
        "ultimo_host": str(net.broadcast_address - 1),
        "hosts_utilizables": net.num_addresses - 2,
    }


def main() -> None:
    """Arranca el servidor MCP usando stdio (entrada y salida estándar)."""
    mcp.run(transport="stdio")
