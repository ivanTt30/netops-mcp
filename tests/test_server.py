"""Tests del protocolo MCP: un cliente real habla con el servidor en memoria."""

import pytest
from mcp import Client

from netops_mcp.server import mcp

# Todos los tests de este archivo son asíncronos y los ejecuta anyio
pytestmark = pytest.mark.anyio

TOOLS_ESPERADAS = {
    "calcular_subred",
    "comprobar_ip_en_red",
    "dividir_vlsm",
    "resolver_dns",
    "comprobar_puerto",
    "hacer_ping",
    "generar_config_switch",
    "generar_config_router",
}


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_el_servidor_publica_todas_las_tools():
    async with Client(mcp) as client:
        tools = (await client.list_tools()).tools
    assert {tool.name for tool in tools} == TOOLS_ESPERADAS
    # Todas tienen descripción y esquema de salida
    assert all(tool.description for tool in tools)
    assert all(tool.output_schema for tool in tools)


async def test_calcular_subred_devuelve_datos_estructurados():
    async with Client(mcp) as client:
        resultado = await client.call_tool("calcular_subred", {"red": "172.16.5.9/20"})
    assert not resultado.is_error
    assert resultado.structured_content["red"] == "172.16.0.0"
    assert resultado.structured_content["broadcast"] == "172.16.15.255"


async def test_error_legible_para_el_modelo():
    async with Client(mcp) as client:
        resultado = await client.call_tool("calcular_subred", {"red": "hola"})
    assert resultado.is_error
    assert "no es una red IPv4 válida" in resultado.content[0].text


async def test_ping_bloquea_inyeccion_de_comandos():
    async with Client(mcp) as client:
        resultado = await client.call_tool("hacer_ping", {"host": "8.8.8.8; rm -rf /"})
    assert resultado.is_error
    assert "no es una IP ni un nombre de host válido" in resultado.content[0].text


async def test_resources():
    async with Client(mcp) as client:
        uris = {str(r.uri) for r in (await client.list_resources()).resources}
        contenido = await client.read_resource("netops://subred/10.0.0.0/22")
    assert uris == {"netops://referencia/puertos", "netops://referencia/cidr"}
    assert '"broadcast": "10.0.3.255"' in contenido.contents[0].text


async def test_prompts():
    async with Client(mcp) as client:
        nombres = {p.name for p in (await client.list_prompts()).prompts}
        prompt = await client.get_prompt(
            "disenar_red", {"red_base": "192.168.0.0/24", "departamentos": "Ventas: 50"}
        )
    assert nombres == {"disenar_red", "diagnosticar_conectividad"}
    assert "dividir_vlsm" in prompt.messages[0].content.text
