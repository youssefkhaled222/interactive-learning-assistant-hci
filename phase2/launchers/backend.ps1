$ErrorActionPreference = 'Stop'
$phase = Split-Path -Parent $PSScriptRoot
Set-Location $phase
$env:HCI_REQUIRE_NEXT = '1'
Write-Host '[HCI 1/4] Python broker: 127.0.0.1 TCP 8765 + WebSocket 8766.'
& (Join-Path $phase '.venv\Scripts\python.exe') 'backend\server.py'
