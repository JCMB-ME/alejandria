$ErrorActionPreference = 'SilentlyContinue'

Write-Host '=== Looking for Docker Desktop ==='
$dockerPaths = @(
  'C:\Program Files\Docker\Docker\Docker Desktop.exe',
  'C:\Program Files\Docker Desktop\Docker Desktop.exe',
  "$env:LOCALAPPDATA\Docker\Docker Desktop.exe",
  "$env:LOCALAPPDATA\Programs\Docker\Docker Desktop.exe"
)
foreach ($p in $dockerPaths) {
  if (Test-Path $p) {
    Write-Host "FOUND: $p"
  }
}

Write-Host ''
Write-Host '=== Looking for docker CLI ==='
$cli = Get-ChildItem 'C:\' -Recurse -Filter 'docker.exe' -ErrorAction SilentlyContinue -Depth 5 | Select-Object -First 5 -ExpandProperty FullName
foreach ($c in $cli) {
  Write-Host "FOUND: $c"
}

Write-Host ''
Write-Host '=== Looking for docker.exe in PATH ==='
$cmd = Get-Command docker.exe -ErrorAction SilentlyContinue
if ($cmd) {
  Write-Host "FOUND in PATH: $($cmd.Source)"
} else {
  Write-Host 'NOT FOUND in PATH'
}

Write-Host ''
Write-Host '=== Docker Desktop process running? ==='
Get-Process -Name 'Docker Desktop' -ErrorAction SilentlyContinue | Select-Object ProcessName, Id | Format-Table -AutoSize

Write-Host ''
Write-Host '=== WSL distributions ==='
wsl -l -v 2>&1 | Out-String | Write-Host