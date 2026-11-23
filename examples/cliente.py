"""Cliente MCP de prueba: arranca netops-mcp y habla con él por stdio."""

import json
import sys

import anyio
from mcp import Client, StdioServerParameters


async def main() -> None:
    # 1. Cómo arrancar el servidor: con este mismo Python, ejecutando el paquete
    servidor = StdioServerParameters(command=sys.executable, args=["-m", "netops_mcp"])

    # 2. Conectarse: lanza el servidor y hace el saludo inicial del protocolo
    async with Client(servidor) as client:
        # 3. Preguntar qué tools ofrece
        resultado = await client.list_tools()
        for tool in resultado.tools:
            print(f"Tool: {tool.name}")
            print(f"  Descripción: {tool.description.splitlines()[0]}")
            print(f"  Esquema de entrada: {json.dumps(tool.input_schema)}")

        # 4. Llamar a una tool, igual que haría Claude
        respuesta = await client.call_tool("calcular_subred", {"red": "10.0.0.0/22"})
        print("\nRespuesta de calcular_subred:")
        print(respuesta.content[0].text)


if __name__ == "__main__":
    anyio.run(main)
