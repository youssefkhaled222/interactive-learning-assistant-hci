$ErrorActionPreference = 'Stop'
$phase = Split-Path -Parent $PSScriptRoot
Set-Location $phase
Write-Host '[HCI 4/4] MediaPipe hand tracking with opt-in real guarded gameplay.'
& (Join-Path $phase '.venv\Scripts\python.exe') 'backend\hand_pointer_preview.py' --enable-gameplay
