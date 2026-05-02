$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Frontend = Join-Path $Root "frontend"
$Node = "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
$Pnpm = Join-Path $Root "tools\pnpm\bin\pnpm.cjs"

if (-not (Test-Path $Node)) {
  throw "Bundled Node.js was not found. Expected: $Node"
}

if (-not (Test-Path $Pnpm)) {
  throw "Project-local pnpm was not found. Expected: $Pnpm"
}

$env:PATH = "$(Split-Path $Node);$env:PATH"
Set-Location $Frontend
& $Node $Pnpm run build
