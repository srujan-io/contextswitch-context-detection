$ErrorActionPreference = 'Stop'
$IntegrationRoot = Split-Path -Parent $PSScriptRoot
Push-Location $IntegrationRoot
try {
    # Starting twice is harmless: the running instance already serves the UI
    # and extension. Use restart.ps1 explicitly when loading backend changes.
    try {
        $running = Invoke-RestMethod 'http://127.0.0.1:8001/system/state' -TimeoutSec 2
    } catch { $running = $null }
    if ($running -and $running.build -like 'contextswitch-*') {
        Write-Host "ContextSwitch is already running ($($running.build))."
        Write-Host 'Open http://127.0.0.1:8001/ or click the extension icon.'
        Write-Host 'To reload backend changes, run ./scripts/restart.ps1 instead.'
        return
    }
    $occupied = Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue
    if ($occupied) {
        throw "Port 8001 is occupied by another service (PID $($occupied[0].OwningProcess)). No process was stopped."
    }
    & ./.venv/Scripts/python.exe -m uvicorn integration:app --app-dir backend --host 127.0.0.1 --port 8001 --workers 1
    if ($LASTEXITCODE -ne 0) { throw 'ContextSwitch could not start. Check the server output above.' }
} finally { Pop-Location }
