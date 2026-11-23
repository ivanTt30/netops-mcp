"""Tests de los cálculos de subredes."""

import pytest

from netops_mcp.subnetting import (
    SubnettingError,
    ip_in_network,
    prefijo_para_hosts,
    subnet_info,
    vlsm,
)


def test_subred_tipica_de_examen():
    info = subnet_info("192.168.1.37/26")
    assert info.red == "192.168.1.0"
    assert info.mascara == "255.255.255.192"
    assert info.wildcard == "0.0.0.63"
    assert info.broadcast == "192.168.1.63"
    assert info.primer_host == "192.168.1.1"
    assert info.ultimo_host == "192.168.1.62"
    assert info.hosts_utilizables == 62


@pytest.mark.parametrize(
    ("red", "hosts_esperados"),
    [
        ("10.0.0.0/24", 254),
        ("10.0.0.0/30", 2),
        ("10.0.0.0/31", 2),  # enlace punto a punto (RFC 3021)
        ("8.8.8.8/32", 1),  # un solo equipo: el bug que arreglamos
    ],
)
def test_hosts_utilizables(red, hosts_esperados):
    assert subnet_info(red).hosts_utilizables == hosts_esperados


@pytest.mark.parametrize(
    ("red", "tipo"),
    [
        ("192.168.0.0/16", "privada (RFC 1918)"),
        ("8.8.8.0/24", "pública"),
        ("127.0.0.0/8", "loopback"),
        ("169.254.0.0/16", "link-local (APIPA)"),
    ],
)
def test_tipo_de_red(red, tipo):
    assert subnet_info(red).tipo == tipo


@pytest.mark.parametrize("entrada_mala", ["hola", "300.1.1.1/24", "192.168.1.0/40", ""])
def test_red_invalida_da_error(entrada_mala):
    with pytest.raises(SubnettingError):
        subnet_info(entrada_mala)


def test_ip_en_red():
    red = "192.168.1.128/26"
    assert ip_in_network("192.168.1.130", red).papel == "host utilizable"
    assert ip_in_network("192.168.1.128", red).papel == "dirección de red (no se puede asignar)"
    assert ip_in_network("192.168.1.191", red).papel == "broadcast (no se puede asignar)"
    assert ip_in_network("192.168.1.10", red).pertenece is False


@pytest.mark.parametrize(("hosts", "prefijo"), [(2, 30), (12, 28), (50, 26), (100, 25)])
def test_prefijo_para_hosts(hosts, prefijo):
    assert prefijo_para_hosts(hosts) == prefijo


def test_vlsm_ordena_y_no_solapa():
    resultado = vlsm("192.168.1.0/24", {"Ventas": 50, "Informatica": 100, "RRHH": 20, "WAN": 2})
    assert [s.nombre for s in resultado.subredes] == ["Informatica", "Ventas", "RRHH", "WAN"]
    assert [s.subred for s in resultado.subredes] == [
        "192.168.1.0/25",
        "192.168.1.128/26",
        "192.168.1.192/27",
        "192.168.1.224/30",
    ]
    assert resultado.direcciones_libres == 28


def test_vlsm_sin_espacio_da_error():
    with pytest.raises(SubnettingError, match="No queda espacio"):
        vlsm("192.168.1.0/26", {"A": 30, "B": 30, "C": 30})
