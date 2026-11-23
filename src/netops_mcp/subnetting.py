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



class IpCheck(BaseModel):
    """Resultado de comprobar si una IP pertenece a una red."""

    ip: str
    red: str
    pertenece: bool
    papel: str


def ip_in_network(ip: str, red: str) -> IpCheck:
    """Comprueba si una IP pertenece a una red y qué papel tiene en ella."""
    try:
        direccion = ipaddress.IPv4Address(ip.strip())
    except ValueError:
        raise SubnettingError(f"'{ip}' no es una dirección IPv4 válida.") from None

    net = parse_network(red)

    if direccion not in net:
        papel = "fuera de la red"
    elif net.prefixlen >= 31:
        papel = "host utilizable"
    elif direccion == net.network_address:
        papel = "dirección de red (no se puede asignar)"
    elif direccion == net.broadcast_address:
        papel = "broadcast (no se puede asignar)"
    else:
        papel = "host utilizable"

    return IpCheck(ip=str(direccion), red=str(net), pertenece=direccion in net, papel=papel)



def prefijo_para_hosts(hosts: int) -> int:
    """Devuelve el prefijo más ajustado que admite ese número de hosts."""
    if hosts < 1:
        raise SubnettingError("El número de hosts debe ser al menos 1.")
    for prefijo in range(30, 0, -1):
        if 2 ** (32 - prefijo) - 2 >= hosts:
            return prefijo
    raise SubnettingError(f"No existe una red IPv4 con {hosts} hosts.")


class SubredVlsm(BaseModel):
    """Una subred asignada por VLSM."""

    nombre: str
    hosts_pedidos: int
    subred: str
    mascara: str
    primer_host: str
    ultimo_host: str
    broadcast: str
    hosts_sobrantes: int


class VlsmResult(BaseModel):
    """Resultado completo del reparto VLSM."""

    red_base: str
    subredes: list[SubredVlsm]
    direcciones_libres: int


def vlsm(red_base: str, necesidades: dict[str, int]) -> VlsmResult:
    """Reparte una red entre varias subredes con VLSM (de mayor a menor)."""
    base = parse_network(red_base)

    # 1. Ordenar de mayor a menor número de hosts, como se hace a mano
    ordenadas = sorted(necesidades.items(), key=lambda par: par[1], reverse=True)

    # 2. Trabajar con las IPs como números para poder sumar
    siguiente = int(base.network_address)  # primera dirección libre
    final = int(base.broadcast_address)  # última dirección de la red base
    subredes = []

    for nombre, hosts in ordenadas:
        prefijo = prefijo_para_hosts(hosts)
        tamano = 2 ** (32 - prefijo)

        if siguiente + tamano - 1 > final:
            raise SubnettingError(
                f"No queda espacio en {base} para '{nombre}' ({hosts} hosts)."
            )

        info = subnet_info(f"{ipaddress.IPv4Address(siguiente)}/{prefijo}")
        subredes.append(
            SubredVlsm(
                nombre=nombre,
                hosts_pedidos=hosts,
                subred=f"{info.red}{info.cidr}",
                mascara=info.mascara,
                primer_host=info.primer_host,
                ultimo_host=info.ultimo_host,
                broadcast=info.broadcast,
                hosts_sobrantes=info.hosts_utilizables - hosts,
            )
        )
        siguiente += tamano  # 3. La siguiente subred empieza justo después

    return VlsmResult(
        red_base=str(base),
        subredes=subredes,
        direcciones_libres=final - siguiente + 1,
    )
