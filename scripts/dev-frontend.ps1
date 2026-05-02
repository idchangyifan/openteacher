$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Frontend = Join-Path $Root "frontend"
$Node = "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
$Vite = Join-Path $Frontend "node_modules\vite\bin\vite.js"

if (-not (Test-Path $Node)) {
  throw "Bundled Node.js was not found. Expected: $Node"
}

if (-not (Test-Path $Vite)) {
  throw "Vite was not found. Run frontend dependency installation first. Expected: $Vite"
}

$env:PATH = "$(Split-Path $Node);$env:PATH"
Set-Location $Frontend
& $Node $Vite --host 127.0.0.1 --port 5173
