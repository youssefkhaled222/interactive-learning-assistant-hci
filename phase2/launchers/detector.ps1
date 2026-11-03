$ErrorActionPreference = 'Stop'
$phase = Split-Path -Parent $PSScriptRoot
Set-Location $phase
$python = Join-Path $HOME 'Projects\.venv-hci-detector\Scripts\python.exe'
if (-not (Test-Path $python)) { throw "Missing YOLO Python environment: $python" }
Write-Host '[HCI 3/4] Real YOLO11s model (CPU), webcam index 0, local preview 8767.'
& $python 'backend\object_detector.py' --model yolo11s.pt --camera 0 --device cpu --image-size 640 --publish --stream --no-window
