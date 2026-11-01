$ErrorActionPreference='Stop'
$IntegrationRoot=(Resolve-Path (Split-Path -Parent $PSScriptRoot)).Path
$resumeCamera=$false
try { $oldState=Invoke-RestMethod http://127.0.0.1:8001/system/state -TimeoutSec 2; $resumeCamera=$oldState.sensors.CAMERA.status -eq 'TRACKING' } catch {}
$listeners=Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue
foreach($listener in $listeners) {
    $server=Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)"
    $launcher=Get-CimInstance Win32_Process -Filter "ProcessId = $($server.ParentProcessId)"
    $owned=$server.CommandLine.Contains($IntegrationRoot) -or ($launcher -and $launcher.CommandLine.Contains($IntegrationRoot) -and $launcher.CommandLine.Contains('integration:app'))
    if (!$owned -or !$server.CommandLine.Contains('integration:app')) {
        throw "Port 8001 belongs to another application (PID $($server.ProcessId)); it was not stopped."
    }
    Stop-Process -Id $server.ProcessId
    if($launcher -and $launcher.CommandLine.Contains((Join-Path $IntegrationRoot '.venv')) -and $launcher.CommandLine.Contains('integration:app')) { Stop-Process -Id $launcher.ProcessId -ErrorAction SilentlyContinue }
}
$serverProcess=Start-Process -FilePath (Join-Path $IntegrationRoot '.venv/Scripts/python.exe') -ArgumentList @('-m','uvicorn','integration:app','--app-dir','backend','--host','127.0.0.1','--port','8001','--workers','1') -WorkingDirectory $IntegrationRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $IntegrationRoot 'server.stdout.log') -RedirectStandardError (Join-Path $IntegrationRoot 'server.stderr.log') -PassThru
for($attempt=0;$attempt -lt 40;$attempt++) {
    Start-Sleep -Milliseconds 250
    try {
        $state=Invoke-RestMethod http://127.0.0.1:8001/system/state -TimeoutSec 1
        if($state.build) {
            if($resumeCamera){Invoke-RestMethod http://127.0.0.1:8001/system/camera -Method Post -ContentType 'application/json' -Body '{"paused":false}' | Out-Null}
            Write-Host "ContextSwitch started: $($state.build) (PID $($serverProcess.Id))"
            exit 0
        }
    } catch {}
}
throw 'Server did not become healthy. Inspect server.stderr.log.'
