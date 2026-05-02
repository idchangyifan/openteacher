param(
  [switch]$Reload
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Backend = Join-Path $Root "backend"
$Python = Join-Path $Backend ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
  throw "Backend virtual environment is missing. Expected: $Python"
}

Set-Location $Backend
$Args = @("app.main:app", "--host", "127.0.0.1", "--port", "8000")

if ($Reload) {
  $Args += "--reload"
}

& $Python -m uvicorn @Args
