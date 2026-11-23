"""Servidor MCP de netops-mcp: herramientas de redes para Claude."""

from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from . import subnetting

mcp = MCPServer(name="netops-mcp")


@mcp.tool()
def calcular_subred(
    red: Annotated[str, Field(description="Red en CIDR, p. ej. 192.168.1.0/24")],
) -> subnetting.SubnetInfo:
    """Calcula red, máscara, wildcard, broadcast, rango de hosts y tipo de una red IPv4."""
    try:
        return subnetting.subnet_info(red)
    except subnetting.SubnettingError as error:
        raise ToolError(str(error)) from None


def main() -> None:
    """Arranca el servidor MCP usando stdio (entrada y salida estándar)."""
    mcp.run(transport="stdio")
