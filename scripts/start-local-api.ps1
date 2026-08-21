$ErrorActionPreference = "Stop"

$workspaceRoot = Split-Path -Parent $PSScriptRoot
$apiDirectory = Join-Path $workspaceRoot "services\api"
$environmentFile = Join-Path $apiDirectory ".env"
$environmentTemplate = Join-Path $apiDirectory "local.env.example"
$pythonExecutable = Join-Path $workspaceRoot ".venv\Scripts\python.exe"
$localDataDirectory = Join-Path $workspaceRoot "data\local"

if (-not (Test-Path -LiteralPath $environmentFile)) {
    throw "Missing services/api/.env. Run: Copy-Item services/api/local.env.example services/api/.env, then replace the placeholder secrets."
}

$environmentText = Get-Content -LiteralPath $environmentFile -Raw
if ($environmentText -match "replace-with-") {
    throw "services/api/.env still contains replace-with-* placeholders. Set JWT_SECRET and INITIAL_ADMIN_PASSWORD first."
}

$adminPasswordMatch = [regex]::Match(
    $environmentText,
    "(?m)^INITIAL_ADMIN_PASSWORD\s*=\s*(.+?)\s*$"
)
if (-not $adminPasswordMatch.Success -or $adminPasswordMatch.Groups[1].Value.Length -lt 12) {
    throw "INITIAL_ADMIN_PASSWORD in services/api/.env must contain at least 12 characters."
}

$jwtSecretMatch = [regex]::Match(
    $environmentText,
    "(?m)^JWT_SECRET\s*=\s*(.+?)\s*$"
)
if (-not $jwtSecretMatch.Success -or $jwtSecretMatch.Groups[1].Value.Length -lt 32) {
    throw "JWT_SECRET in services/api/.env must contain at least 32 characters."
}

if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    throw "Missing .venv. Create it and install services/api/requirements.txt before starting the API."
}

New-Item -ItemType Directory -Path $localDataDirectory -Force | Out-Null

Push-Location $apiDirectory
try {
    & $pythonExecutable -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw "Database migration failed with exit code $LASTEXITCODE." }

    & $pythonExecutable -m app.bootstrap
    if ($LASTEXITCODE -ne 0) { throw "Initial administrator setup failed with exit code $LASTEXITCODE." }

    Write-Host "API starting at http://127.0.0.1:8000 (Ctrl+C to stop)"
    & $pythonExecutable -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
    if ($LASTEXITCODE -ne 0) { throw "API exited with code $LASTEXITCODE." }
}
finally {
    Pop-Location
}
