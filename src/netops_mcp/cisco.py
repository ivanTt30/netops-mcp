"""Generador de configuraciones Cisco IOS (sin nada de MCP).

Solo genera texto: no se conecta a ningún equipo.
"""
import ipaddress
import re

from pydantic import BaseModel

from .subnetting import SubnettingError, parse_network
# Interfaces válidas: Gi0/1, Fa0/1-12, GigabitEthernet0/0/1...
PATRON_INTERFAZ = re.compile(
    r"^(GigabitEthernet|FastEthernet|Ethernet|Gi|Fa|Eth?)\d+(/\d+){0,2}(-\d+)?$",
    re.IGNORECASE,
)
PATRON_NOMBRE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")


class CiscoConfigError(ValueError):
    """Un dato para generar la configuración no es válido."""


class PasoConfig(BaseModel):
    """Un paso de la configuración: qué se hace y con qué comandos."""

    titulo: str
    explicacion: str
    comandos: list[str]


class ConfigResult(BaseModel):
    """Configuración completa: por pasos y como texto listo para pegar."""

    pasos: list[PasoConfig]
    config_completa: str


def validar_vlan(vlan_id: int) -> None:
    if not 1 <= vlan_id <= 4094:
        raise CiscoConfigError(f"La VLAN {vlan_id} no es válida (1-4094).")
    if 1002 <= vlan_id <= 1005:
        raise CiscoConfigError(f"Las VLAN 1002-1005 están reservadas (pediste la {vlan_id}).")


def validar_interfaz(nombre: str) -> str:
    nombre = nombre.strip()
    if not PATRON_INTERFAZ.match(nombre):
        raise CiscoConfigError(f"'{nombre}' no parece una interfaz Cisco (ej.: Gi0/1, Fa0/1-12).")
    return nombre


def validar_nombre(nombre: str) -> str:
    nombre = nombre.strip().replace(" ", "_")
    if not PATRON_NOMBRE.match(nombre):
        raise CiscoConfigError(f"Nombre '{nombre}' no válido: usa letras, números, '_' o '-'.")
    return nombre


def comando_interfaz(interfaz: str) -> str:
    """Un rango (Fa0/1-12) necesita 'interface range'."""
    return f"interface range {interfaz}" if "-" in interfaz else f"interface {interfaz}"


def unir_pasos(pasos: list[PasoConfig]) -> ConfigResult:
    """Junta los pasos en un único texto con comentarios '!' de Cisco."""
    bloques = []
    for numero, paso in enumerate(pasos, start=1):
        comandos = "\n".join(paso.comandos)
        bloques.append(f"! Paso {numero}: {paso.titulo}\n! {paso.explicacion}\n{comandos}")
    return ConfigResult(pasos=pasos, config_completa="\n\n".join(bloques))


def config_vlans_switch(
    vlans: dict[int, str],
    puertos_acceso: dict[str, int],
    puerto_trunk: str | None = None,
) -> ConfigResult:
    """Configura VLANs, puertos de acceso y un trunk en un switch."""
    if not vlans:
        raise CiscoConfigError("Indica al menos una VLAN.")
    for vlan_id in vlans:
        validar_vlan(vlan_id)

    # Paso 1: crear las VLANs
    comandos = ["enable", "configure terminal"]
    for vlan_id, nombre in sorted(vlans.items()):
        comandos += [f"vlan {vlan_id}", f" name {validar_nombre(nombre)}", " exit"]
    pasos = [
        PasoConfig(
            titulo="Crear las VLANs",
            explicacion="Damos de alta cada VLAN con un nombre descriptivo.",
            comandos=comandos,
        )
    ]

    # Paso 2: puertos de acceso
    if puertos_acceso:
        comandos = []
        for interfaz, vlan_id in puertos_acceso.items():
            if vlan_id not in vlans:
                raise CiscoConfigError(f"La VLAN {vlan_id} de {interfaz} no está en la lista.")
            comandos += [
                comando_interfaz(validar_interfaz(interfaz)),
                " switchport mode access",
                f" switchport access vlan {vlan_id}",
                " spanning-tree portfast",
                " no shutdown",
                " exit",
            ]
        pasos.append(
            PasoConfig(
                titulo="Asignar puertos de acceso",
                explicacion="Los puertos de los equipos finales van en modo acceso en su VLAN.",
                comandos=comandos,
            )
        )

    # Paso 3: enlace troncal
    if puerto_trunk:
        permitidas = ",".join(str(v) for v in sorted(vlans))
        pasos.append(
            PasoConfig(
                titulo="Configurar el enlace troncal",
                explicacion="El trunk lleva todas las VLANs etiquetadas (802.1Q) hacia el router.",
                comandos=[
                    comando_interfaz(validar_interfaz(puerto_trunk)),
                    " switchport mode trunk",
                    f" switchport trunk allowed vlan {permitidas}",
                    " no shutdown",
                    " exit",
                ],
            )
        )

    # Último paso: guardar y verificar
    pasos.append(
        PasoConfig(
            titulo="Guardar y verificar",
            explicacion="Guardamos la configuración y comprobamos VLANs y trunk.",
            comandos=[
                "end",
                "copy running-config startup-config",
                "show vlan brief",
                "show interfaces trunk",
            ],
        )
    )
    return unir_pasos(pasos)


def config_router_on_a_stick(
    interfaz: str,
    subredes: dict[int, str],
    con_dhcp: bool = True,
    dns: str = "8.8.8.8",
) -> ConfigResult:
    """Router-on-a-stick: una subinterfaz por VLAN (gateway = primera IP) y DHCP opcional."""
    interfaz = validar_interfaz(interfaz)
    if "-" in interfaz:
        raise CiscoConfigError("La interfaz del router debe ser una sola, no un rango.")
    if not subredes:
        raise CiscoConfigError("Indica al menos una VLAN con su subred.")
    try:
        ipaddress.IPv4Address(dns)
    except ValueError:
        raise CiscoConfigError(f"El DNS '{dns}' no es una IPv4 válida.") from None

    # Validar y convertir cada subred
    redes: dict[int, ipaddress.IPv4Network] = {}
    for vlan_id, texto in sorted(subredes.items()):
        validar_vlan(vlan_id)
        try:
            redes[vlan_id] = parse_network(texto)
        except SubnettingError as error:
            raise CiscoConfigError(str(error)) from None

    # Paso 1: activar la interfaz física (no lleva IP)
    pasos = [
        PasoConfig(
            titulo="Activar la interfaz física",
            explicacion="La interfaz que va al switch no lleva IP; solo hay que levantarla.",
            comandos=[
                "enable",
                "configure terminal",
                f"interface {interfaz}",
                " no shutdown",
                " exit",
            ],
        )
    ]

    # Paso 2: una subinterfaz por VLAN
    comandos = []
    for vlan_id, red in redes.items():
        gateway = red.network_address + 1
        comandos += [
            f"interface {interfaz}.{vlan_id}",
            f" encapsulation dot1Q {vlan_id}",
            f" ip address {gateway} {red.netmask}",
            " exit",
        ]
    pasos.append(
        PasoConfig(
            titulo="Crear una subinterfaz por VLAN",
            explicacion="Cada subinterfaz es la puerta de enlace de su VLAN (primera IP de la red).",
            comandos=comandos,
        )
    )

    # Pasos 3 y 4: DHCP
    if con_dhcp:
        pasos.append(
            PasoConfig(
                titulo="Excluir las puertas de enlace del DHCP",
                explicacion="Así el router nunca reparte la IP que él mismo usa.",
                comandos=[
                    f"ip dhcp excluded-address {r.network_address + 1}" for r in redes.values()
                ],
            )
        )
        comandos = []
        for vlan_id, red in redes.items():
            comandos += [
                f"ip dhcp pool VLAN{vlan_id}",
                f" network {red.network_address} {red.netmask}",
                f" default-router {red.network_address + 1}",
                f" dns-server {dns}",
                " exit",
            ]
        pasos.append(
            PasoConfig(
                titulo="Crear un pool DHCP por VLAN",
                explicacion="Cada VLAN recibe IPs de su subred, con su gateway y su DNS.",
                comandos=comandos,
            )
        )

    # Último paso: guardar y verificar
    verificar = ["end", "copy running-config startup-config", "show ip interface brief"]
    if con_dhcp:
        verificar.append("show ip dhcp binding")
    pasos.append(
        PasoConfig(
            titulo="Guardar y verificar",
            explicacion="Guardamos y comprobamos las subinterfaces y las IPs repartidas.",
            comandos=verificar,
        )
    )
    return unir_pasos(pasos)
