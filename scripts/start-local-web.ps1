$ErrorActionPreference = "Stop"

$workspaceRoot = Split-Path -Parent $PSScriptRoot
$webDirectory = Join-Path $workspaceRoot "apps\web"
$nodeModulesDirectory = Join-Path $webDirectory "node_modules"
$npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue

if (-not $npmCommand) {
    $standardNodeDirectory = "C:\Program Files\nodejs"
    $standardNpm = Join-Path $standardNodeDirectory "npm.cmd"
    if (-not (Test-Path -LiteralPath $standardNpm)) {
        throw "npm was not found. Install Node.js 22 LTS or newer before starting the Web app."
    }
    $env:Path = "$standardNodeDirectory;$env:Path"
    $npmExecutable = $standardNpm
}
else {
    $npmExecutable = $npmCommand.Source
}

if (-not (Test-Path -LiteralPath $nodeModulesDirectory)) {
    throw "Missing apps/web/node_modules. Run npm install in apps/web before starting the Web app."
}

Push-Location $webDirectory
try {
    Write-Host "Web app starting at http://127.0.0.1:5173 (Ctrl+C to stop)"
    & $npmExecutable run dev -- --host 127.0.0.1 --port 5173
    if ($LASTEXITCODE -ne 0) { throw "Web app exited with code $LASTEXITCODE." }
}
finally {
    Pop-Location
}
