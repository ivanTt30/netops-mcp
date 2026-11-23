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
@mcp.tool()
def comprobar_ip_en_red(
    ip: Annotated[str, Field(description="Dirección IPv4, p. ej. 192.168.1.130")],
    red: Annotated[str, Field(description="Red en CIDR, p. ej. 192.168.1.128/26")],
) -> subnetting.IpCheck:
    """Indica si una IP pertenece a una red y si es de red, broadcast o un host utilizable."""
    try:
        return subnetting.ip_in_network(ip, red)
    except subnetting.SubnettingError as error:
        raise ToolError(str(error)) from None

def main() -> None:
    """Arranca el servidor MCP usando stdio (entrada y salida estándar)."""
    mcp.run(transport="stdio")
