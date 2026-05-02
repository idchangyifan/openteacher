param(
  [int]$TimeoutSeconds = 600
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$LogDir = Join-Path $Root "logs"
$LogFile = Join-Path $LogDir "docker-post-reboot.log"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-SetupLog {
  param([string]$Message)
  $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
  Add-Content -Path $LogFile -Value $line
  Write-Host $line
}

Write-SetupLog "Starting Docker post-reboot setup."

$machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$env:Path = "$machinePath;$userPath"

try {
  Start-Service com.docker.service -ErrorAction SilentlyContinue
  Write-SetupLog "Docker service start requested."
} catch {
  Write-SetupLog "Docker service start failed: $($_.Exception.Message)"
}

$dockerDesktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
if (Test-Path $dockerDesktop) {
  Start-Process -WindowStyle Hidden -FilePath $dockerDesktop
  Write-SetupLog "Docker Desktop start requested."
}

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
do {
  Start-Sleep -Seconds 5
  try {
    docker info *> $null
    if ($LASTEXITCODE -eq 0) {
      Write-SetupLog "Docker engine is ready."
      break
    }
  } catch {
    Write-SetupLog "Waiting for Docker engine: $($_.Exception.Message)"
  }
} while ((Get-Date) -lt $deadline)

docker info *> $null
if ($LASTEXITCODE -ne 0) {
  Write-SetupLog "Docker engine did not become ready before timeout."
  exit 1
}

Set-Location $Root
docker compose up -d postgres
if ($LASTEXITCODE -ne 0) {
  Write-SetupLog "docker compose up failed."
  exit 1
}

Write-SetupLog "PostgreSQL container requested."
docker compose ps | Out-String | Add-Content -Path $LogFile
Write-SetupLog "Docker post-reboot setup completed."
