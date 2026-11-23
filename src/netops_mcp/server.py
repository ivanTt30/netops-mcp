"""Servidor MCP de netops-mcp: herramientas de redes para Claude."""

from typing import Annotated

import anyio
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from . import diagnostics, subnetting

mcp = MCPServer(
    name="netops-mcp",
    instructions=(
        "Herramientas de redes: cálculo de subredes IPv4, VLSM y comprobación de IPs, "
        "y diagnóstico real (DNS, ping y puertos TCP) desde el equipo donde se ejecuta. "
        "Usa SIEMPRE estas herramientas para cálculos de direccionamiento y diagnósticos "
        "en lugar de calcularlos tú o usar otros comandos."
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

# Estas tools salen a la red real: se lo indicamos al cliente con "annotations"
SONDA_DE_RED = ToolAnnotations(read_only_hint=True, open_world_hint=True)


@mcp.tool(annotations=SONDA_DE_RED)
async def resolver_dns(
    dominio: Annotated[str, Field(description="Nombre a resolver, p. ej. github.com")],
) -> diagnostics.DnsResult:
    """Resuelve un dominio a sus direcciones IPv4 e IPv6 con el DNS del equipo."""
    try:
        return await anyio.to_thread.run_sync(diagnostics.resolver_dns, dominio)
    except diagnostics.DiagnosticsError as error:
        raise ToolError(str(error)) from None


@mcp.tool(annotations=SONDA_DE_RED)
async def comprobar_puerto(
    host: Annotated[str, Field(description="IP o nombre del equipo")],
    puerto: Annotated[int, Field(ge=1, le=65535, description="Puerto TCP, p. ej. 443")],
) -> diagnostics.PortResult:
    """Comprueba si un puerto TCP de un equipo está abierto, cerrado o filtrado."""
    try:
        return await anyio.to_thread.run_sync(diagnostics.comprobar_puerto, host, puerto)
    except diagnostics.DiagnosticsError as error:
        raise ToolError(str(error)) from None


@mcp.tool(annotations=SONDA_DE_RED)
async def hacer_ping(
    host: Annotated[str, Field(description="IP o nombre del equipo")],
    paquetes: Annotated[int, Field(ge=1, le=10, description="Número de paquetes")] = 4,
) -> diagnostics.PingResult:
    """Hace ping a un equipo: indica si responde, el % de pérdida y la latencia."""
    try:
        return await anyio.to_thread.run_sync(diagnostics.hacer_ping, host, paquetes)
    except diagnostics.DiagnosticsError as error:
        raise ToolError(str(error)) from None

def main() -> None:
    """Arranca el servidor MCP usando stdio (entrada y salida estándar)."""
    mcp.run(transport="stdio")
