import asyncio
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from pydantic import AnyUrl

from mcp import ClientSession
from mcp.client.auth import OAuthClientProvider
from mcp.client.streamable_http import streamablehttp_client
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken

from ..utils import logger

try:
    from config import ROBINHOOD_MCP_TOKEN_PATH, ROBINHOOD_MCP_URL
except ImportError:
    ROBINHOOD_MCP_URL = "https://agent.robinhood.com/mcp/trading"
    ROBINHOOD_MCP_TOKEN_PATH = ".robinhood_mcp_tokens.json"

OAUTH_REDIRECT_URI = "http://localhost:8765/callback"
OAUTH_SCOPE = "internal"
DEFAULT_TOKEN_PATH = Path(__file__).resolve().parents[2] / ROBINHOOD_MCP_TOKEN_PATH


class FileTokenStorage:
    def __init__(self, path: Path):
        self.path = path

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    async def get_tokens(self) -> OAuthToken | None:
        data = self._load()
        if not data.get("tokens"):
            return None
        return OAuthToken.model_validate(data["tokens"])

    async def set_tokens(self, tokens: OAuthToken) -> None:
        data = self._load()
        data["tokens"] = tokens.model_dump(mode="json")
        self._save(data)

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        data = self._load()
        if not data.get("client_info"):
            return None
        return OAuthClientInformationFull.model_validate(data["client_info"])

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        data = self._load()
        data["client_info"] = client_info.model_dump(mode="json")
        self._save(data)


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    auth_code: str | None = None
    auth_state: str | None = None

    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        _OAuthCallbackHandler.auth_code = query.get("code", [None])[0]
        _OAuthCallbackHandler.auth_state = query.get("state", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(
            b"<html><body><h1>Robinhood MCP connected</h1>"
            b"<p>You can close this tab and return to the bot.</p></body></html>"
        )

    def log_message(self, format, *args):
        return


class RobinhoodMCPClient:
    def __init__(self, token_path: Path = DEFAULT_TOKEN_PATH):
        self.token_path = token_path
        self._session: ClientSession | None = None
        self._transport_ctx = None
        self._session_ctx = None
        self._lock = asyncio.Lock()

    async def _redirect_handler(self, auth_url: str) -> None:
        logger.info("Opening browser for Robinhood MCP authentication...")
        logger.info(f"If the browser does not open, visit: {auth_url}")
        webbrowser.open(auth_url)

    async def _callback_handler(self) -> tuple[str, str | None]:
        _OAuthCallbackHandler.auth_code = None
        _OAuthCallbackHandler.auth_state = None
        server = HTTPServer(("localhost", 8765), _OAuthCallbackHandler)
        thread = threading.Thread(target=server.handle_request, daemon=True)
        thread.start()

        for _ in range(300):
            if _OAuthCallbackHandler.auth_code:
                server.server_close()
                return _OAuthCallbackHandler.auth_code, _OAuthCallbackHandler.auth_state
            await asyncio.sleep(1)

        raise TimeoutError("Timed out waiting for Robinhood OAuth callback on http://localhost:8765/callback")

    async def connect(self) -> None:
        async with self._lock:
            if self._session is not None:
                return

            oauth_auth = OAuthClientProvider(
                server_url=ROBINHOOD_MCP_URL,
                client_metadata=OAuthClientMetadata(
                    client_name="Robinhood AI Trading Bot",
                    redirect_uris=[AnyUrl(OAUTH_REDIRECT_URI)],
                    grant_types=["authorization_code", "refresh_token"],
                    response_types=["code"],
                    scope=OAUTH_SCOPE,
                ),
                storage=FileTokenStorage(self.token_path),
                redirect_handler=self._redirect_handler,
                callback_handler=self._callback_handler,
            )

            self._transport_ctx = streamablehttp_client(
                ROBINHOOD_MCP_URL,
                auth=oauth_auth,
                timeout=120.0,
                sse_read_timeout=300.0,
            )
            read, write, _ = await self._transport_ctx.__aenter__()
            self._session_ctx = ClientSession(read, write)
            self._session = await self._session_ctx.__aenter__()
            await self._session.initialize()
            tools = await self._session.list_tools()
            logger.info(f"Connected to Robinhood MCP ({len(tools.tools)} tools available)")

    async def disconnect(self) -> None:
        async with self._lock:
            if self._session_ctx is not None:
                await self._session_ctx.__aexit__(None, None, None)
                self._session_ctx = None
                self._session = None
            if self._transport_ctx is not None:
                await self._transport_ctx.__aexit__(None, None, None)
                self._transport_ctx = None

    async def call_tool(self, name: str, arguments: dict | None = None):
        if self._session is None:
            await self.connect()

        result = await self._session.call_tool(name, arguments or {})
        if result.isError:
            message = _extract_tool_text(result)
            raise Exception(f"MCP tool {name} failed: {message}")

        payload = _parse_tool_payload(_extract_tool_text(result))
        return _unwrap_tool_payload(payload)


_client = RobinhoodMCPClient()


def get_client() -> RobinhoodMCPClient:
    return _client


def _extract_tool_text(result) -> str:
    parts = []
    for block in result.content:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "".join(parts).strip()


def _parse_tool_payload(text: str):
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _unwrap_tool_payload(payload):
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload
