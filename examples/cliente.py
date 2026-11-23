"""Cliente MCP de prueba: arranca netops-mcp y habla con él por stdio."""

import json
import sys

import anyio
from mcp import Client, StdioServerParameters


def mostrar(datos: object) -> None:
    """Imprime un diccionario como JSON bonito."""
    print(json.dumps(datos, indent=2, ensure_ascii=False))


async def main() -> None:
    servidor = StdioServerParameters(command=sys.executable, args=["-m", "netops_mcp"])

    async with Client(servidor) as client:
        print("Tools del servidor:")
        for tool in (await client.list_tools()).tools:
            print(f"- {tool.name}: {tool.description}")

        print("\n>>> calcular_subred 172.16.5.9/20")
        r = await client.call_tool("calcular_subred", {"red": "172.16.5.9/20"})
        mostrar(r.structured_content)

        print("\n>>> comprobar_ip_en_red 192.168.1.191 en 192.168.1.128/26")
        r = await client.call_tool(
            "comprobar_ip_en_red", {"ip": "192.168.1.191", "red": "192.168.1.128/26"}
        )
        mostrar(r.structured_content)


if __name__ == "__main__":
    anyio.run(main)
