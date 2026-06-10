# Run the trading bot continuously on Windows (foreground).
Set-Location $PSScriptRoot\..

if (-not (Test-Path ".env")) {
    Write-Error ".env not found. Copy .env.example to .env and configure it."
    exit 1
}

if (-not (Test-Path ".robinhood_mcp_tokens.json")) {
    Write-Error "Robinhood MCP tokens not found. Run: python scripts/auth_robinhood.py"
    exit 1
}

$env:AUTO_CONFIRM = "true"
python main.py
