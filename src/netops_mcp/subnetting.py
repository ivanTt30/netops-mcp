"""Cálculos de subredes IPv4 (sin nada de MCP)."""

import ipaddress

from pydantic import BaseModel

REDES_PRIVADAS = [
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.168.0.0/16"),
]


class SubnettingError(ValueError):
    """La red recibida no es válida."""


class SubnetInfo(BaseModel):
    """Resultado de calcular una subred."""

    red: str
    cidr: str
    mascara: str
    wildcard: str
    broadcast: str
    primer_host: str
    ultimo_host: str
    hosts_utilizables: int
    tipo: str


def parse_network(red: str) -> ipaddress.IPv4Network:
    """Convierte un texto como '192.168.1.37/26' en un objeto de red."""
    try:
        return ipaddress.IPv4Network(red.strip(), strict=False)
    except ValueError:
        raise SubnettingError(
            f"'{red}' no es una red IPv4 válida. Usa formato CIDR, ej. 192.168.1.0/24."
        ) from None


def tipo_de_red(net: ipaddress.IPv4Network) -> str:
    """Dice si la red es privada, pública, loopback..."""
    if net.is_loopback:
        return "loopback"
    if net.is_link_local:
        return "link-local (APIPA)"
    if net.is_multicast:
        return "multicast"
    if any(net.subnet_of(privada) for privada in REDES_PRIVADAS):
        return "privada (RFC 1918)"
    if not net.is_global:
        return "reservada"
    return "pública"


def subnet_info(red: str) -> SubnetInfo:
    """Calcula toda la información de una subred IPv4."""
    net = parse_network(red)

    # /31 y /32 no reservan dirección de red ni broadcast
    if net.prefixlen >= 31:
        primero, ultimo = net.network_address, net.broadcast_address
        hosts = net.num_addresses
    else:
        primero, ultimo = net.network_address + 1, net.broadcast_address - 1
        hosts = net.num_addresses - 2

    return SubnetInfo(
        red=str(net.network_address),
        cidr=f"/{net.prefixlen}",
        mascara=str(net.netmask),
        wildcard=str(net.hostmask),
        broadcast=str(net.broadcast_address),
        primer_host=str(primero),
        ultimo_host=str(ultimo),
        hosts_utilizables=hosts,
        tipo=tipo_de_red(net),
    )
