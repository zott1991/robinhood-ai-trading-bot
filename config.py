import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Credentials
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Robinhood MCP (official Agentic Trading server)
ROBINHOOD_MCP_URL = os.getenv("ROBINHOOD_MCP_URL", "https://agent.robinhood.com/mcp/trading")
ROBINHOOD_MCP_TOKEN_PATH = os.getenv("ROBINHOOD_MCP_TOKEN_PATH", ".robinhood_mcp_tokens.json")
ROBINHOOD_AGENTIC_ACCOUNT_NUMBER = os.getenv("ROBINHOOD_AGENTIC_ACCOUNT_NUMBER", "")

# Basic config parameters
MODE = os.getenv("MODE", "auto")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
RUN_INTERVAL_SECONDS = int(os.getenv("RUN_INTERVAL_SECONDS", "600"))

# Robinhood config parameters
TRADE_EXCEPTIONS = [s.strip() for s in os.getenv("TRADE_EXCEPTIONS", "").split(",") if s.strip()]
WATCHLIST_NAMES = [s.strip() for s in os.getenv("WATCHLIST_NAMES", "My First List").split(",") if s.strip()]
WATCHLIST_OVERVIEW_LIMIT = int(os.getenv("WATCHLIST_OVERVIEW_LIMIT", "10"))
PORTFOLIO_LIMIT = int(os.getenv("PORTFOLIO_LIMIT", "10"))

def _parse_amount(value, default):
    if value is None or value == "":
        return default
    if value.lower() == "false":
        return False
    return float(value)

MIN_SELLING_AMOUNT_USD = _parse_amount(os.getenv("MIN_SELLING_AMOUNT_USD"), 1.0)
MAX_SELLING_AMOUNT_USD = _parse_amount(os.getenv("MAX_SELLING_AMOUNT_USD"), 10.0)
MIN_BUYING_AMOUNT_USD = _parse_amount(os.getenv("MIN_BUYING_AMOUNT_USD"), 1.0)
MAX_BUYING_AMOUNT_USD = _parse_amount(os.getenv("MAX_BUYING_AMOUNT_USD"), 10.0)

# OpenAI config params
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")
