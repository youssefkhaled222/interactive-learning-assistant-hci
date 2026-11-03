# Phase II one-command local demo launcher. Run after v5 tests pass.
# Four visible consoles; no fake sensor events or browser-submitted answers.
$ErrorActionPreference = 'Stop'
$phase = $PSScriptRoot
$launchers = @('backend.ps1','frontend.ps1','detector.ps1','hand.ps1')
Write-Host 'Starting HCI Phase II in four separate PowerShell windows.'
Write-Host 'Do not start pose_tracker.py on camera 0 simultaneously with YOLO.'
foreach ($scriptName in $launchers) {
    $scriptPath = Join-Path $phase "launchers\$scriptName"
    if (-not (Test-Path -LiteralPath $scriptPath)) { throw "Missing launcher: $scriptPath" }
    Start-Process -FilePath 'powershell.exe' -WorkingDirectory $phase `
        -ArgumentList "-NoExit -ExecutionPolicy Bypass -File `"$scriptPath`""
    Start-Sleep -Milliseconds 1500
}
Write-Host 'Open http://127.0.0.1:5173 after the Vite terminal shows the ready URL.'
Write-Host 'The real backend owns answer verification. See PHASE2_DEMO_SCRIPT.md.'
