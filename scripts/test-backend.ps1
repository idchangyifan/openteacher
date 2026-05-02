$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Backend = Join-Path $Root "backend"
$Python = Join-Path $Backend ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
  throw "Backend virtual environment is missing. Expected: $Python"
}

Set-Location $Backend
$env:PYTEST_ADDOPTS = "-p no:cacheprovider"
& $Python -m pytest
& $Python -m ruff check app tests
