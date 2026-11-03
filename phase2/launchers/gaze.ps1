$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$model = '.\models\face_landmarker.task'
if (-not (Test-Path $model)) {
    Write-Host 'Face model missing. Run .\Download-Gaze-Model.cmd first.' -ForegroundColor Yellow
    exit 2
}
$camera = 1
if ($env:HCI_GAZE_CAMERA -match '^\d+$') { $camera = [int]$env:HCI_GAZE_CAMERA }
Write-Host "Starting REAL player-facing gaze tracker on camera $camera..."
& '.\.venv\Scripts\python.exe' '.\backend\gaze_tracker.py' --camera $camera --model $model
if ($LASTEXITCODE -ne 0) { Write-Host "Gaze tracker stopped with exit code $LASTEXITCODE" -ForegroundColor Yellow }
