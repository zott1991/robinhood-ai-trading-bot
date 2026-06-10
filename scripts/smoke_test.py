"""Quick Robinhood MCP connectivity test without OpenAI."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api import robinhood
from src.utils import logger


async def main():
    login = await robinhood.login_to_robinhood()
    if not login:
        raise SystemExit("Robinhood MCP login failed")

    account = await robinhood.get_account_info()
    positions = await robinhood.get_portfolio_stocks()
    logger.info(f"Buying power: ${account['buying_power']}")
    logger.info(f"Open positions: {len(positions)}")

    if positions:
        for symbol, data in positions.items():
            logger.info(f"  {symbol}: qty={data['quantity']} price={data['price']}")
    else:
        logger.info("No open positions in the agentic account.")

    for watchlist_name in []:
        pass

    from config import WATCHLIST_NAMES

    for watchlist_name in WATCHLIST_NAMES:
        stocks = await robinhood.get_watchlist_stocks(watchlist_name)
        logger.info(f"Watchlist '{watchlist_name}': {len(stocks)} instrument(s)")
        if stocks:
            logger.info(f"  Sample: {', '.join(stock['symbol'] for stock in stocks[:5])}")

    logger.info("Robinhood MCP smoke test passed.")


if __name__ == "__main__":
    asyncio.run(main())
