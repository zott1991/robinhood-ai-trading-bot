"""Validate local setup before running the trading bot."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def ok(message):
    print(f"[ok] {message}")


def warn(message):
    print(f"[warn] {message}")


def fail(message):
    print(f"[fail] {message}")


def main():
    issues = 0

    if importlib.util.find_spec("config") is None:
        fail("config.py is missing")
        issues += 1
    else:
        ok("config.py found")

    try:
        import config
    except Exception as exc:
        fail(f"Could not import config.py: {exc}")
        return 1

    if not config.OPENAI_API_KEY or config.OPENAI_API_KEY in ("...", "your-openai-api-key"):
        fail("OPENAI_API_KEY is not set. Add it to .env or config.py")
        issues += 1
    else:
        ok("OPENAI_API_KEY is set")

    token_path = ROOT / config.ROBINHOOD_MCP_TOKEN_PATH
    if token_path.exists():
        ok(f"Robinhood MCP tokens found at {config.ROBINHOOD_MCP_TOKEN_PATH}")
    else:
        warn(
            "Robinhood MCP tokens not found. Run: python scripts/auth_robinhood.py"
        )
        issues += 1

    if config.ROBINHOOD_AGENTIC_ACCOUNT_NUMBER:
        ok(f"Agentic account configured: ...{config.ROBINHOOD_AGENTIC_ACCOUNT_NUMBER[-4:]}")
    else:
        fail("ROBINHOOD_AGENTIC_ACCOUNT_NUMBER is not set")
        issues += 1

    if config.WATCHLIST_NAMES:
        ok(f"Watchlists configured: {', '.join(config.WATCHLIST_NAMES)}")
    else:
        warn("WATCHLIST_NAMES is empty. The bot will only trade existing portfolio positions.")

    ok(f"Mode: {config.MODE}")

    if issues:
        print(f"\nSetup incomplete: {issues} issue(s) to fix.")
        return 1

    print("\nSetup looks good. Run: python main.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
