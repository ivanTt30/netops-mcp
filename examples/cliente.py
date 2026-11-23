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

        print("\n>>> dividir_vlsm 192.168.10.0/24")
        r = await client.call_tool(
            "dividir_vlsm",
            {
                "red_base": "192.168.10.0/24",
                "subredes": [
                    {"nombre": "Alumnos", "hosts": 60},
                    {"nombre": "Profesores", "hosts": 25},
                    {"nombre": "Servidores", "hosts": 10},
                ],
            },
        )
        for s in r.structured_content["subredes"]:
            print(f"{s['nombre']:<12} {s['subred']:<18} gateway {s['primer_host']}")

        print("\n>>> dividir_vlsm con hosts = 0 (error de validación)")
        r = await client.call_tool(
            "dividir_vlsm",
            {"red_base": "192.168.10.0/24", "subredes": [{"nombre": "X", "hosts": 0}]},
        )
        print(r.content[0].text)


if __name__ == "__main__":
    anyio.run(main)
