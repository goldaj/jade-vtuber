# Installation unique du lanceur sur D:, hors du clone Git.
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if (-not (Test-Path -LiteralPath 'D:\' -PathType Container)) {
    throw 'Disque D: introuvable. Le launcher Jade est prevu pour ce poste avec D:.'
}
$target = 'D:\Jade\launcher'
New-Item -ItemType Directory -Force -Path $target | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'jade-launcher.ps1') -Destination (Join-Path $target 'JadeLauncher.ps1') -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'jade-runner.ps1') -Destination (Join-Path $target 'JadeRunner.ps1') -Force

$settingsPath = Join-Path $target 'launcher.json'
$settings = @{ repo = $repo; secretsFile = '' }
if (Test-Path -LiteralPath $settingsPath) {
    $previous = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json
    if ($previous.secretsFile) { $settings.secretsFile = [string]$previous.secretsFile }
}
$settings | ConvertTo-Json | Set-Content -LiteralPath $settingsPath -Encoding UTF8
@'
@echo off
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0JadeLauncher.ps1"
'@ | Set-Content -LiteralPath (Join-Path $target 'Lancer-Jade.cmd') -Encoding ASCII

Write-Host "Launcher installe : $target\Lancer-Jade.cmd"
Write-Host 'Tu peux creer un raccourci vers ce fichier sur le Bureau.'
Write-Host "Depot Git : $repo"
Write-Host "Aucun programme ni appel OpenAI n'a ete demarre."
