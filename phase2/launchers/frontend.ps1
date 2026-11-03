$ErrorActionPreference = 'Stop'
$phase = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $phase 'frontend')
Write-Host '[HCI 2/4] React browser: http://127.0.0.1:5173'
& npm.cmd run dev
