"""Servidor MCP de netops-mcp: herramientas de redes para Claude."""

from typing import Annotated

import anyio
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ResourceError, ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from . import cisco, diagnostics, reference, subnetting

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
# Estas tools solo generan texto: no tocan ningún equipo ni salen a la red
SOLO_TEXTO = ToolAnnotations(read_only_hint=True, open_world_hint=False)


class Vlan(BaseModel):
    """Una VLAN del switch."""

    id: Annotated[int, Field(ge=1, le=4094, description="Número de VLAN, p. ej. 10")]
    nombre: Annotated[str, Field(description="Nombre de la VLAN, p. ej. ALUMNOS")]


class PuertoAcceso(BaseModel):
    """Puertos de equipos finales y la VLAN a la que pertenecen."""

    interfaz: Annotated[str, Field(description="Interfaz o rango, p. ej. Fa0/1-12")]
    vlan: Annotated[int, Field(description="VLAN de esos puertos")]


class SubredVlan(BaseModel):
    """Subred asociada a una VLAN."""

    vlan: Annotated[int, Field(description="Número de VLAN")]
    red: Annotated[str, Field(description="Subred en CIDR, p. ej. 192.168.10.0/26")]


@mcp.tool(annotations=SOLO_TEXTO)
def generar_config_switch(
    vlans: Annotated[list[Vlan], Field(min_length=1)],
    puertos_acceso: list[PuertoAcceso] | None = None,
    puerto_trunk: Annotated[
        str | None, Field(description="Puerto troncal hacia el router, p. ej. Gi0/1")
    ] = None,
) -> cisco.ConfigResult:
    """Genera paso a paso la configuración Cisco IOS de un switch: VLANs, accesos y trunk."""
    try:
        return cisco.config_vlans_switch(
            vlans={v.id: v.nombre for v in vlans},
            puertos_acceso={p.interfaz: p.vlan for p in puertos_acceso or []},
            puerto_trunk=puerto_trunk,
        )
    except cisco.CiscoConfigError as error:
        raise ToolError(str(error)) from None


@mcp.tool(annotations=SOLO_TEXTO)
def generar_config_router(
    interfaz: Annotated[str, Field(description="Interfaz hacia el switch, p. ej. Gi0/0")],
    subredes: Annotated[list[SubredVlan], Field(min_length=1)],
    con_dhcp: bool = True,
    dns: Annotated[str, Field(description="Servidor DNS para los clientes DHCP")] = "8.8.8.8",
) -> cisco.ConfigResult:
    """Genera la configuración router-on-a-stick: subinterfaces 802.1Q por VLAN y DHCP."""
    try:
        return cisco.config_router_on_a_stick(
            interfaz=interfaz,
            subredes={s.vlan: s.red for s in subredes},
            con_dhcp=con_dhcp,
            dns=dns,
        )
    except cisco.CiscoConfigError as error:
        raise ToolError(str(error)) from None

# --- Resources: datos de consulta que el usuario o la app pueden adjuntar ---


@mcp.resource(
    "netops://referencia/puertos",
    title="Puertos bien conocidos",
    description="Tabla de puertos y servicios habituales (SSH, DNS, HTTP, MQTT...).",
    mime_type="text/markdown",
)
def recurso_puertos() -> str:
    return reference.tabla_puertos()


@mcp.resource(
    "netops://referencia/cidr",
    title="Chuleta CIDR",
    description="Máscara, wildcard y hosts útiles de /8 a /32.",
    mime_type="text/markdown",
)
def recurso_cidr() -> str:
    return reference.tabla_cidr()


@mcp.resource(
    "netops://subred/{ip}/{prefijo}",
    title="Información de una subred",
    description="Datos de cualquier subred, p. ej. netops://subred/192.168.1.0/24",
    mime_type="application/json",
)
def recurso_subred(ip: str, prefijo: str) -> str:
    try:
        return subnetting.subnet_info(f"{ip}/{prefijo}").model_dump_json(indent=2)
    except subnetting.SubnettingError as error:
        raise ResourceError(str(error)) from None

# --- Prompts: plantillas de tareas que el usuario elige desde el cliente ---


@mcp.prompt(title="Diseñar una red con VLANs")
def disenar_red(red_base: str, departamentos: str) -> str:
    """Diseña el direccionamiento VLSM, las VLANs y la configuración de switch y router."""
    return (
        f"Quiero diseñar una red a partir de {red_base} para estos departamentos "
        f"(nombre: hosts): {departamentos}.\n\n"
        "1. Usa `dividir_vlsm` para repartir la red.\n"
        "2. Asigna una VLAN a cada departamento (10, 20, 30...).\n"
        "3. Usa `generar_config_switch` para el switch y `generar_config_router` "
        "para el router, con DHCP.\n"
        "4. Presenta primero una tabla resumen y después la configuración paso a paso, "
        "explicando brevemente cada paso antes de sus comandos."
    )


@mcp.prompt(title="Diagnosticar conectividad")
def diagnosticar_conectividad(host: str, puerto: str = "443") -> str:
    """Diagnóstico por capas de un equipo o servicio que no responde."""
    return (
        f"No consigo conectarme a {host} (puerto {puerto}). Diagnostícalo por capas:\n"
        "1. `resolver_dns`: ¿el nombre resuelve a una IP? (capa de aplicación, DNS)\n"
        "2. `hacer_ping`: ¿el equipo es alcanzable? (capa de red, ICMP)\n"
        f"3. `comprobar_puerto` en el {puerto}: ¿el servicio escucha? (capa de transporte, TCP)\n"
        "Explica qué indica cada resultado y cuál es la causa más probable del problema."
    )

def main() -> None:
    """Arranca el servidor MCP usando stdio (entrada y salida estándar)."""
    mcp.run(transport="stdio")
