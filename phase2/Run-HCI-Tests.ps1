$ErrorActionPreference = 'Stop'
$phase = $PSScriptRoot
Set-Location $phase
$python = Join-Path $phase '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw "Missing Python virtual environment: $python" }
Write-Host 'Running all backend unit and integration tests...'
& $python -m unittest discover -s tests
if ($LASTEXITCODE -ne 0) { throw "Python tests failed: $LASTEXITCODE" }
Set-Location (Join-Path $phase 'frontend')
Write-Host 'Running all React unit tests...'
& npm.cmd test
if ($LASTEXITCODE -ne 0) { throw "React tests failed: $LASTEXITCODE" }
Write-Host 'Building React for production...'
& npm.cmd run build
if ($LASTEXITCODE -ne 0) { throw "React build failed: $LASTEXITCODE" }
Write-Host 'PASS: automated software tests and frontend build.'
