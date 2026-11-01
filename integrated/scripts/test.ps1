$ErrorActionPreference = 'Stop'
$IntegrationRoot = Split-Path -Parent $PSScriptRoot
Push-Location $IntegrationRoot
try {
    & ./.venv/Scripts/python.exe -m pytest tests -q
    if ($LASTEXITCODE -ne 0) { throw 'Integration Python tests failed' }
    & ./.venv/Scripts/python.exe -m unittest discover -s backend/voice -p test_actions.py
    if ($LASTEXITCODE -ne 0) { throw 'Voice regression tests failed' }
    & node --test extension/tests/*.cjs
    if ($LASTEXITCODE -ne 0) { throw 'Extension tests failed' }
    Push-Location frontend
    try {
        & npm test
        if ($LASTEXITCODE -ne 0) { throw 'Frontend tests failed' }
        & npm run typecheck
        if ($LASTEXITCODE -ne 0) { throw 'Typecheck failed' }
    } finally { Pop-Location }
} finally { Pop-Location }
