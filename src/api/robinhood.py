import uuid
from datetime import datetime

import pandas as pd
import yfinance as yf
from pytz import timezone

from .mcp_client import get_client
from ..utils import logger
from config import MODE, ROBINHOOD_AGENTIC_ACCOUNT_NUMBER

account_info_cache = {}


async def login_to_robinhood():
    try:
        await get_client().connect()
        account_number = await _resolve_agentic_account_number()
        account_info_cache["account_number"] = account_number
        return {"expires_in": 3600, "account_number": account_number}
    except Exception as e:
        logger.error(f"Failed to connect to Robinhood MCP: {e}")
        return None


def is_market_open():
    eastern = timezone("US/Eastern")
    now = datetime.now(eastern)
    if now.weekday() >= 5:
        return False
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now <= market_close


def round_money(price, decimals=2):
    if price is None:
        return None
    return round(float(price), decimals)


def round_quantity(quantity, decimals=6):
    if quantity is None:
        return None
    return round(float(quantity), decimals)


def extract_my_stocks_data(stock_data):
    return {
        "current_price": round_money(stock_data["price"]),
        "my_quantity": round_quantity(stock_data["quantity"]),
        "my_average_buy_price": round_money(stock_data["average_buy_price"]),
    }


def extract_watchlist_data(stock_data):
    return {
        "current_price": round_money(stock_data["price"]),
        "my_quantity": round_quantity(0),
        "my_average_buy_price": round_money(0),
    }


def extract_sell_response_data(sell_resp):
    order = _extract_order(sell_resp)
    return {
        "quantity": round_quantity(_first_value(order, "quantity", "cumulative_quantity")),
        "price": round_money(_first_value(order, "average_price", "price")),
    }


def extract_buy_response_data(buy_resp):
    order = _extract_order(buy_resp)
    return {
        "quantity": round_quantity(_first_value(order, "quantity", "cumulative_quantity")),
        "price": round_money(_first_value(order, "average_price", "price")),
    }


def enrich_with_rsi(stock_data, historical_data, symbol):
    if len(historical_data) < 14:
        logger.debug(f"Not enough data to calculate RSI for {symbol}")
        return stock_data

    prices = [round_money(day["close_price"]) for day in historical_data]
    delta = pd.Series(prices).diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=14).mean().iloc[-1]
    avg_loss = loss.rolling(window=14).mean().iloc[-1]
    if avg_loss == 0:
        rs = 100
    else:
        rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    stock_data["rsi"] = round(float(rsi), 2)
    return stock_data


def enrich_with_vwap(stock_data, historical_data, symbol):
    if len(historical_data) < 1:
        logger.debug(f"Not enough data to calculate VWAP for {symbol}")
        return stock_data

    stock_history_df = pd.DataFrame(historical_data)
    stock_history_df["close_price"] = pd.to_numeric(stock_history_df["close_price"], errors="coerce")
    stock_history_df["high_price"] = pd.to_numeric(stock_history_df["high_price"], errors="coerce")
    stock_history_df["low_price"] = pd.to_numeric(stock_history_df["low_price"], errors="coerce")
    stock_history_df["volume"] = pd.to_numeric(stock_history_df["volume"], errors="coerce")
    stock_history_df = stock_history_df[stock_history_df["volume"] > 0]
    stock_history_df["typical_price"] = (
        stock_history_df["high_price"] + stock_history_df["low_price"] + stock_history_df["close_price"]
    ) / 3

    sum_of_volumes = stock_history_df["volume"].sum()
    dot_product = stock_history_df["volume"].dot(stock_history_df["typical_price"])
    if sum_of_volumes == 0:
        logger.debug(f"Total volume is zero for {symbol}, cannot compute VWAP")
        return stock_data

    stock_data["vwap"] = round_money(dot_product / sum_of_volumes)
    return stock_data


def enrich_with_moving_averages(stock_data, historical_data, symbol):
    if len(historical_data) < 200:
        logger.debug(f"Not enough data to calculate moving averages for {symbol}")
        return stock_data

    prices = [round_money(day["close_price"]) for day in historical_data]
    moving_avg_50 = pd.Series(prices).rolling(window=50).mean().iloc[-1]
    moving_avg_200 = pd.Series(prices).rolling(window=200).mean().iloc[-1]
    stock_data["50_day_mavg_price"] = round_money(moving_avg_50)
    stock_data["200_day_mavg_price"] = round_money(moving_avg_200)
    return stock_data


def enrich_with_analyst_ratings(stock_data, ratings_data):
    stock_data["analyst_summary"] = ratings_data["summary"]
    stock_data["analyst_ratings"] = ratings_data["ratings"]
    return stock_data


async def enrich_with_pdt_restrictions(stock_data, symbol):
    try:
        tradability = await get_equity_tradability(symbol)
        results = _as_list(tradability, "results")
        result = next((item for item in results if item.get("symbol") == symbol), None)
        if not result:
            stock_data["is_buy_pdt_restricted"] = False
            stock_data["is_sell_pdt_restricted"] = False
            return stock_data

        tradeable = result.get("tradeable", True)
        stock_data["is_buy_pdt_restricted"] = not tradeable
        stock_data["is_sell_pdt_restricted"] = not tradeable
    except Exception as e:
        logger.debug(f"Could not fetch tradability for {symbol}: {e}")
        stock_data["is_buy_pdt_restricted"] = False
        stock_data["is_sell_pdt_restricted"] = False
    return stock_data


async def get_account_info():
    account_number = await _get_account_number()
    portfolio = await get_client().call_tool("get_portfolio", {"account_number": account_number})
    buying_power_obj = portfolio.get("buying_power") if isinstance(portfolio, dict) else None
    buying_power = None
    if isinstance(buying_power_obj, dict):
        buying_power = buying_power_obj.get("buying_power")
    if buying_power is None:
        buying_power = portfolio.get("cash") if isinstance(portfolio, dict) else None
    if buying_power is None:
        raise Exception("Error getting buying power from Robinhood MCP portfolio")

    resp = {"buying_power": round_money(buying_power)}
    account_info_cache["portfolio"] = portfolio
    return resp


async def get_portfolio_stocks():
    account_number = await _get_account_number()
    positions = await get_client().call_tool("get_equity_positions", {"account_number": account_number})
    position_list = _as_list(positions, "positions")
    symbols = [position["symbol"] for position in position_list if position.get("symbol")]
    quotes = await _get_quotes_map(symbols)

    holdings = {}
    for position in position_list:
        symbol = position.get("symbol")
        if not symbol:
            continue
        quote = quotes.get(symbol, {})
        holdings[symbol] = {
            "price": quote.get("last_trade_price"),
            "quantity": position.get("quantity"),
            "average_buy_price": position.get("average_buy_price") or 0,
        }
    return holdings


async def get_watchlist_stocks(name):
    watchlists = await get_client().call_tool("get_watchlists", {})
    watchlist_list = _as_list(watchlists, "watchlists")
    list_id = None
    for watchlist in watchlist_list:
        if watchlist.get("display_name", "").lower() == name.lower():
            list_id = watchlist.get("id")
            break

    if list_id is None:
        raise Exception(f"Watchlist '{name}' not found")

    items = await get_client().call_tool("get_watchlist_items", {"list_id": list_id})
    item_list = _as_list(items, "items")
    symbols = [
        item["symbol"]
        for item in item_list
        if item.get("object_type") == "instrument" and item.get("symbol")
    ]

    quotes = await _get_quotes_map(symbols)
    results = []
    for symbol in symbols:
        quote = quotes.get(symbol, {})
        results.append({"symbol": symbol, "price": quote.get("last_trade_price")})
    return results


def get_ratings(symbol):
    logger.debug(f"Analyst ratings are not available via Robinhood MCP; skipping {symbol}")
    return {
        "summary": {"num_buy_ratings": 0, "num_hold_ratings": 0, "num_sell_ratings": 0},
        "ratings": [],
    }


def get_historical_data(symbol, interval="day", span="year"):
    period, yf_interval = _map_history_request(interval, span)
    ticker = yf.Ticker(symbol)
    history = ticker.history(period=period, interval=yf_interval)
    if history.empty:
        raise Exception(f"Error getting historical data for {symbol}: No response")

    rows = []
    for timestamp, row in history.iterrows():
        rows.append(
            {
                "begins_at": timestamp.isoformat(),
                "close_price": float(row["Close"]),
                "high_price": float(row["High"]),
                "low_price": float(row["Low"]),
                "open_price": float(row["Open"]),
                "volume": float(row["Volume"]),
            }
        )
    return rows


async def sell_stock(symbol, quantity):
    if MODE == "demo":
        return {"id": "demo"}

    if MODE == "manual":
        confirm = input(f"Confirm sell for {symbol} of {quantity}? (yes/no): ")
        if confirm.lower() != "yes":
            return {"id": "cancelled"}

    order = await _build_market_order(symbol, "sell", quantity)
    await get_client().call_tool("review_equity_order", order)
    response = await get_client().call_tool("place_equity_order", order)
    return _normalize_order_response(response)


async def buy_stock(symbol, quantity):
    if MODE == "demo":
        return {"id": "demo"}

    if MODE == "manual":
        confirm = input(f"Confirm buy for {symbol} of {quantity}? (yes/no): ")
        if confirm.lower() != "yes":
            return {"id": "cancelled"}

    order = await _build_market_order(symbol, "buy", quantity)
    await get_client().call_tool("review_equity_order", order)
    response = await get_client().call_tool("place_equity_order", order)
    return _normalize_order_response(response)


async def get_equity_tradability(symbol):
    account_number = await _get_account_number()
    return await get_client().call_tool(
        "get_equity_tradability",
        {"account_number": account_number, "symbols": [symbol]},
    )


async def _get_quotes_map(symbols):
    if not symbols:
        return {}

    quotes_map = {}
    for chunk_start in range(0, len(symbols), 20):
        chunk = symbols[chunk_start : chunk_start + 20]
        quotes = await get_client().call_tool("get_equity_quotes", {"symbols": chunk})
        for result in _as_list(quotes, "results"):
            quote = result.get("quote", {}) if isinstance(result, dict) else {}
            symbol = quote.get("symbol")
            if symbol:
                quotes_map[symbol] = quote
    return quotes_map


async def _resolve_agentic_account_number():
    if ROBINHOOD_AGENTIC_ACCOUNT_NUMBER:
        return ROBINHOOD_AGENTIC_ACCOUNT_NUMBER

    accounts = await get_client().call_tool("get_accounts", {})
    account_list = _as_list(accounts, "accounts")
    for account in account_list:
        if account.get("agentic_allowed"):
            return account["account_number"]

    raise Exception("No agentic_allowed Robinhood account found. Open an Agentic account first.")


async def _get_account_number():
    if account_info_cache.get("account_number"):
        return account_info_cache["account_number"]
    account_number = await _resolve_agentic_account_number()
    account_info_cache["account_number"] = account_number
    return account_number


async def _build_market_order(symbol, side, quantity):
    account_number = await _get_account_number()
    return {
        "account_number": account_number,
        "symbol": symbol,
        "side": side,
        "type": "market",
        "quantity": str(quantity),
        "time_in_force": "gfd",
        "market_hours": "regular_hours",
        "ref_id": str(uuid.uuid4()),
    }


def _normalize_order_response(response):
    order = _extract_order(response)
    if isinstance(order, dict) and order.get("id"):
        return order
    return response


def _extract_order(response):
    if isinstance(response, dict):
        if "order" in response:
            return response["order"]
        if "id" in response:
            return response
    return response


def _map_history_request(interval, span):
    if interval == "5minute" and span == "day":
        return "1d", "5m"
    if interval == "day" and span == "year":
        return "1y", "1d"
    return "1mo", "1d"


def _as_list(payload, *keys):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def _first_value(payload, *keys):
    if not isinstance(payload, dict):
        return None
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return value
    return None
