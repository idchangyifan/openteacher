$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Script = Join-Path $Root "scripts\finish-docker-setup.ps1"
$TaskName = "OpenTeacherFinishDockerSetup"
$Action = New-ScheduledTaskAction `
  -Execute "powershell.exe" `
  -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Script`""
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Principal = New-ScheduledTaskPrincipal `
  -UserId $env:USERNAME `
  -LogonType Interactive `
  -RunLevel Highest

Register-ScheduledTask `
  -TaskName $TaskName `
  -Action $Action `
  -Trigger $Trigger `
  -Principal $Principal `
  -Force | Out-Null

Write-Host "Registered scheduled task: $TaskName"
