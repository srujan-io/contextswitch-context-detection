param([switch]$Hardware, [string]$Python = 'py')
$ErrorActionPreference = 'Stop'
$IntegrationRoot = Split-Path -Parent $PSScriptRoot
Push-Location $IntegrationRoot
try {
    if (!(Test-Path .venv/Scripts/python.exe)) {
        if ($Python -eq 'py') { & py -3.11 -m venv .venv } else { & $Python -m venv .venv }
        if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 environment creation failed. Supply -Python with its executable path.' }
    }
    $IntegratedPython = Join-Path $IntegrationRoot '.venv/Scripts/python.exe'
    & $IntegratedPython -m ensurepip --upgrade
    if ($LASTEXITCODE -ne 0) { throw 'Could not initialize pip in the integrated environment' }
    & $IntegratedPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed' }
    if ($Hardware) {
        & $IntegratedPython -m pip install -r requirements-hardware.txt
        if ($LASTEXITCODE -ne 0) { throw 'Hardware dependency installation failed' }
    }
    Push-Location frontend
    try {
        & npm ci --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed' }
        & npm run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
        & npm run build:extension
        if ($LASTEXITCODE -ne 0) { throw 'Extension UI build failed' }
    } finally { Pop-Location }
    Write-Host 'Ready. Run ./scripts/start.ps1. Load integrated/extension in Chrome.'
} finally { Pop-Location }
