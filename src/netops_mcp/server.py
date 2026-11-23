"""Servidor MCP de netops-mcp: herramientas de redes para Claude."""

import ipaddress

from mcp.server import MCPServer

mcp = MCPServer(name="netops-mcp")


@mcp.tool()
def calcular_subred(red: str) -> dict:
    """Calcula la dirección de red, máscara, broadcast y rango de hosts de una red IPv4.

    Args:
        red: Red en formato CIDR, por ejemplo 192.168.1.0/24
    """
    net = ipaddress.IPv4Network(red, strict=False)
    return {
        "red": str(net.network_address),
        "mascara": str(net.netmask),
        "broadcast": str(net.broadcast_address),
        "primer_host": str(net.network_address + 1),
        "ultimo_host": str(net.broadcast_address - 1),
        "hosts_utilizables": net.num_addresses - 2,
    }


def main() -> None:
    """Arranca el servidor MCP usando stdio (entrada y salida estándar)."""
    mcp.run(transport="stdio")
