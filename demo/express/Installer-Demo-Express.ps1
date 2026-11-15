# Install the portable demo in user profile; no admin privileges.
$ErrorActionPreference = 'Stop'
$target = Join-Path $env:LOCALAPPDATA 'JadeDemoExpress'
$source = Join-Path $PSScriptRoot 'Jade-Demo-Express.ps1'
if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw 'Demo script missing' }
New-Item -ItemType Directory -Force -Path $target | Out-Null
Copy-Item -LiteralPath $source -Destination (Join-Path $target 'Jade-Demo-Express.ps1') -Force
$launcher = Join-Path $target 'Lancer-Jade-Demo.cmd'
@'
@echo off
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Jade-Demo-Express.ps1"
'@ | Set-Content -LiteralPath $launcher -Encoding ASCII
$menu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
New-Item -ItemType Directory -Force -Path $menu | Out-Null
$link = Join-Path $menu 'Jade Demo Express.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($link)
$shortcut.TargetPath = $launcher
$shortcut.WorkingDirectory = $target
$shortcut.Save()
Write-Host "Installed: $launcher"
Write-Host "Start Menu: Jade Demo Express"
Write-Host "No admin, API account, Python, Poetry or network used."
