$ErrorActionPreference = "Stop"

$workspaceRoot = Split-Path -Parent $PSScriptRoot
$apiDirectory = Join-Path $workspaceRoot "services\api"
$webDirectory = Join-Path $workspaceRoot "apps\web"
$pythonExecutable = Join-Path $workspaceRoot ".venv\Scripts\python.exe"
$pytestTempDirectory = Join-Path $workspaceRoot "tmp\pytest-phase2a-$PID"
$nodeModulesDirectory = Join-Path $webDirectory "node_modules"
$npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue

if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    throw "Missing .venv. Install the backend development dependencies first."
}

if (-not $npmCommand) {
    $standardNodeDirectory = "C:\Program Files\nodejs"
    $standardNpm = Join-Path $standardNodeDirectory "npm.cmd"
    if (-not (Test-Path -LiteralPath $standardNpm)) {
        throw "npm was not found. Install Node.js before running the frontend tests."
    }
    $env:Path = "$standardNodeDirectory;$env:Path"
    $npmExecutable = $standardNpm
}
else {
    $npmExecutable = $npmCommand.Source
}

if (-not (Test-Path -LiteralPath $nodeModulesDirectory)) {
    throw "Missing apps/web/node_modules. Run npm install in apps/web first."
}

Push-Location $apiDirectory
try {
    & $pythonExecutable -m pytest -p no:cacheprovider --basetemp $pytestTempDirectory
    if ($LASTEXITCODE -ne 0) { throw "Backend tests failed with exit code $LASTEXITCODE." }

    & $pythonExecutable -m ruff check --no-cache .
    if ($LASTEXITCODE -ne 0) { throw "Backend lint failed with exit code $LASTEXITCODE." }
}
finally {
    Pop-Location
}

Push-Location $webDirectory
try {
    & $npmExecutable run test:unit
    if ($LASTEXITCODE -ne 0) { throw "Frontend tests failed with exit code $LASTEXITCODE." }

    & $npmExecutable run typecheck
    if ($LASTEXITCODE -ne 0) { throw "Frontend typecheck failed with exit code $LASTEXITCODE." }

    & $npmExecutable run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed with exit code $LASTEXITCODE." }
}
finally {
    Pop-Location
}

Write-Host "Phase 2A automated checks passed."
