"""Datos de referencia que el servidor ofrece como resources."""

PUERTOS_COMUNES = [
    (20, "TCP", "FTP (datos)"),
    (21, "TCP", "FTP (control)"),
    (22, "TCP", "SSH"),
    (23, "TCP", "Telnet (sin cifrar, evitar)"),
    (25, "TCP", "SMTP"),
    (53, "TCP/UDP", "DNS"),
    (67, "UDP", "DHCP servidor"),
    (68, "UDP", "DHCP cliente"),
    (69, "UDP", "TFTP"),
    (80, "TCP", "HTTP"),
    (110, "TCP", "POP3"),
    (123, "UDP", "NTP"),
    (143, "TCP", "IMAP"),
    (161, "UDP", "SNMP"),
    (443, "TCP", "HTTPS"),
    (514, "UDP", "Syslog"),
    (554, "TCP", "RTSP (cámaras IP)"),
    (1883, "TCP", "MQTT (IoT)"),
    (3306, "TCP", "MySQL"),
    (3389, "TCP", "RDP (escritorio remoto)"),
    (5060, "TCP/UDP", "SIP (VoIP)"),
    (8883, "TCP", "MQTT sobre TLS"),
]


def tabla_puertos() -> str:
    """Tabla de puertos en formato Markdown."""
    filas = ["| Puerto | Protocolo | Servicio |", "|---|---|---|"]
    for puerto, protocolo, servicio in PUERTOS_COMUNES:
        filas.append(f"| {puerto} | {protocolo} | {servicio} |")
    return "\n".join(filas)


def a_decimal_con_puntos(numero: int) -> str:
    """Convierte un número de 32 bits en formato 255.255.255.0."""
    return ".".join(str((numero >> desplazamiento) & 255) for desplazamiento in (24, 16, 8, 0))


def tabla_cidr() -> str:
    """Tabla CIDR de /8 a /32 generada automáticamente."""
    filas = ["| CIDR | Máscara | Wildcard | Hosts útiles |", "|---|---|---|---|"]
    for prefijo in range(8, 33):
        mascara = (0xFFFFFFFF << (32 - prefijo)) & 0xFFFFFFFF
        wildcard = ~mascara & 0xFFFFFFFF
        total = 2 ** (32 - prefijo)
        hosts = {32: 1, 31: 2}.get(prefijo, total - 2)
        filas.append(
            f"| /{prefijo} | {a_decimal_con_puntos(mascara)} | "
            f"{a_decimal_con_puntos(wildcard)} | {hosts:,} |".replace(",", ".")
        )
    return "\n".join(filas)
