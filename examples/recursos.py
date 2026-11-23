"""Prueba los resources del servidor netops-mcp."""

import sys

import anyio
from mcp import Client, StdioServerParameters


async def main() -> None:
    servidor = StdioServerParameters(command=sys.executable, args=["-m", "netops_mcp"])

    async with Client(servidor) as client:
        print("Resources fijos:")
        for recurso in (await client.list_resources()).resources:
            print(f"- {recurso.uri}  ({recurso.title})")

        print("\nPlantillas de resources:")
        for plantilla in (await client.list_resource_templates()).resource_templates:
            print(f"- {plantilla.uri_template}  ({plantilla.title})")

        print("\n>>> Leyendo netops://subred/10.0.0.0/22")
        contenido = await client.read_resource("netops://subred/10.0.0.0/22")
        print(contenido.contents[0].text)

        print("\n>>> Leyendo netops://referencia/puertos (primeras líneas)")
        contenido = await client.read_resource("netops://referencia/puertos")
        print("\n".join(contenido.contents[0].text.splitlines()[:6]))


if __name__ == "__main__":
    anyio.run(main)
