"""Diagnóstico de red: DNS, puertos TCP y ping (sin nada de MCP)."""

import ipaddress
import platform
import re
import socket
import subprocess
import time

from pydantic import BaseModel

# Nombre de host válido (RFC 1123): letras, números y guiones separados por puntos,
# sin empezar ni acabar en guion, y como mucho 253 caracteres en total.
PATRON_HOST = re.compile(
    r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*\.?$"
)


class DiagnosticsError(ValueError):
    """El host u otro dato recibido no es válido."""


def validar_host(host: str) -> str:
    """Devuelve el host limpio si es una IP o un nombre válido. Si no, lanza un error."""
    host = host.strip()
    try:
        ipaddress.ip_address(host)  # ¿Es una IP (v4 o v6)?
        return host
    except ValueError:
        pass
    if PATRON_HOST.match(host):  # ¿Es un nombre de host válido?
        return host
    raise DiagnosticsError(f"'{host}' no es una IP ni un nombre de host válido.")


class DnsResult(BaseModel):
    """Resultado de resolver un nombre."""

    dominio: str
    resuelto: bool
    ipv4: list[str] = []
    ipv6: list[str] = []
    error: str | None = None


def resolver_dns(dominio: str) -> DnsResult:
    """Resuelve un nombre a sus IPs usando el DNS configurado en el equipo."""
    host = validar_host(dominio)
    try:
        resultados = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as error:
        return DnsResult(dominio=host, resuelto=False, error=str(error))

    ipv4 = sorted({r[4][0] for r in resultados if r[0] == socket.AF_INET})
    ipv6 = sorted({r[4][0] for r in resultados if r[0] == socket.AF_INET6})
    return DnsResult(dominio=host, resuelto=True, ipv4=ipv4, ipv6=ipv6)


class PortResult(BaseModel):
    """Resultado de comprobar un puerto TCP."""

    host: str
    puerto: int
    abierto: bool
    estado: str
    latencia_ms: float | None = None


def comprobar_puerto(host: str, puerto: int, timeout: float = 3.0) -> PortResult:
    """Intenta abrir una conexión TCP para saber si un puerto está abierto."""
    destino = validar_host(host)
    if not 1 <= puerto <= 65535:
        raise DiagnosticsError("El puerto debe estar entre 1 y 65535.")
    timeout = min(max(timeout, 0.5), 10.0)  # lo dejamos entre 0,5 y 10 segundos

    inicio = time.perf_counter()
    try:
        with socket.create_connection((destino, puerto), timeout=timeout):
            ms = (time.perf_counter() - inicio) * 1000
            return PortResult(
                host=destino,
                puerto=puerto,
                abierto=True,
                estado="abierto",
                latencia_ms=round(ms, 2),
            )
    except TimeoutError:
        estado = "filtrado (no responde: posible firewall)"
    except ConnectionRefusedError:
        estado = "cerrado (el equipo rechaza la conexión)"
    except OSError as error:
        estado = f"error: {error.strerror or error}"
    return PortResult(host=destino, puerto=puerto, abierto=False, estado=estado)


MAX_PAQUETES = 10
PATRON_PERDIDA = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")  # p. ej. "0% packet loss"
PATRON_RTT = re.compile(r"=\s*([\d.]+)/([\d.]+)/([\d.]+)")  # p. ej. "= 11.2/12.5/14.1"


class PingResult(BaseModel):
    """Resultado de un ping."""

    host: str
    alcanzable: bool
    perdida_pct: float | None = None
    rtt_min_ms: float | None = None
    rtt_media_ms: float | None = None
    rtt_max_ms: float | None = None
    error: str | None = None


def comando_ping(host: str, paquetes: int) -> list[str]:
    """Construye el comando ping adecuado para cada sistema operativo."""
    sistema = platform.system()
    if sistema == "Windows":
        return ["ping", "-n", str(paquetes), "-w", "2000", host]
    if sistema == "Darwin":  # macOS: -W va en milisegundos
        return ["ping", "-c", str(paquetes), "-W", "2000", host]
    return ["ping", "-c", str(paquetes), "-W", "2", host]  # Linux: -W va en segundos


def hacer_ping(host: str, paquetes: int = 4) -> PingResult:
    """Hace ping a un host y resume la pérdida de paquetes y la latencia."""
    destino = validar_host(host)
    if not 1 <= paquetes <= MAX_PAQUETES:
        raise DiagnosticsError(f"El número de paquetes debe estar entre 1 y {MAX_PAQUETES}.")

    try:
        # Lista de argumentos y sin shell: imposible inyectar comandos
        proceso = subprocess.run(
            comando_ping(destino, paquetes),
            capture_output=True,
            text=True,
            timeout=paquetes * 3 + 5,
            check=False,
        )
    except FileNotFoundError:
        return PingResult(host=destino, alcanzable=False, error="No está instalado 'ping'.")
    except subprocess.TimeoutExpired:
        return PingResult(host=destino, alcanzable=False, error="El ping tardó demasiado.")

    salida = proceso.stdout
    perdida = PATRON_PERDIDA.search(salida)
    rtt = PATRON_RTT.search(salida)

    return PingResult(
        host=destino,
        alcanzable=proceso.returncode == 0,
        perdida_pct=float(perdida.group(1).replace(",", ".")) if perdida else None,
        rtt_min_ms=float(rtt.group(1)) if rtt else None,
        rtt_media_ms=float(rtt.group(2)) if rtt else None,
        rtt_max_ms=float(rtt.group(3)) if rtt else None,
    )
