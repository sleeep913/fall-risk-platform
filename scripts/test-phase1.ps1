$ErrorActionPreference = 'Stop'

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker was not found. Install Docker Desktop and ensure docker is available in PATH.'
}

docker compose config --quiet
docker compose --profile test build api-test web-test
docker compose --profile test run --rm api-test
docker compose --profile test run --rm web-test

Write-Output 'Phase 1 automated tests passed.'

