"""Servidor MCP de netops-mcp: herramientas de redes para Claude."""

from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field

from . import subnetting

mcp = MCPServer(
    name="netops-mcp",
    instructions=(
        "Herramientas de redes IPv4: cálculo de subredes, VLSM y comprobación de IPs. "
        "Usa SIEMPRE estas herramientas para cualquier cálculo de direccionamiento "
        "en lugar de calcularlo tú, porque sus resultados son exactos y verificados."
    ),
)


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
class RequisitoSubred(BaseModel):
    """Una subred que hay que crear y los hosts que necesita."""

    nombre: Annotated[str, Field(description="Nombre de la subred, p. ej. 'Ventas'")]
    hosts: Annotated[int, Field(ge=1, description="Número de hosts que necesita")]


@mcp.tool()
def dividir_vlsm(
    red_base: Annotated[str, Field(description="Red a repartir, p. ej. 192.168.1.0/24")],
    subredes: Annotated[list[RequisitoSubred], Field(min_length=1)],
) -> subnetting.VlsmResult:
    """Reparte una red entre varias subredes con VLSM (de mayor a menor número de hosts)."""
    nombres = [s.nombre for s in subredes]
    if len(set(nombres)) != len(nombres):
        raise ToolError("Hay nombres de subred repetidos; usa un nombre distinto para cada una.")
    try:
        return subnetting.vlsm(red_base, {s.nombre: s.hosts for s in subredes})
    except subnetting.SubnettingError as error:
        raise ToolError(str(error)) from None

def main() -> None:
    """Arranca el servidor MCP usando stdio (entrada y salida estándar)."""
    mcp.run(transport="stdio")
