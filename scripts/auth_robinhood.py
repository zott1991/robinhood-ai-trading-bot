"""Authenticate with the Robinhood Trading MCP server."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api.mcp_client import get_client
from src.utils import logger


async def main():
    client = get_client()
    await client.connect()
    tools = await client._session.list_tools()
    logger.info(f"Authenticated successfully. {len(tools.tools)} MCP tools available.")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
