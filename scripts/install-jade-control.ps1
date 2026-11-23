param(
    [string] $SecretsFile = 'D:\Codex\private\jade-20261102\jade-actif-20261103.env',
    [string] $PrivateDir = 'D:\Codex\private\jade-runtime',
    [string] $PythonW = 'D:\Codex\caches\venvs\jade-runtime-d-20261114\Scripts\pythonw.exe'
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if (-not (Test-Path -LiteralPath (Join-Path $repo 'tools\jade_pycharm_runner.py') -PathType Leaf)) {
    throw 'Le dossier Jade est incorrect.'
}
if (-not (Test-Path -LiteralPath $SecretsFile -PathType Leaf)) {
    throw "Fichier .env privé absent : $SecretsFile"
}
if (-not (Test-Path -LiteralPath $PythonW -PathType Leaf)) {
    throw "pythonw.exe du venv PyCharm introuvable : $PythonW"
}
New-Item -ItemType Directory -Path $PrivateDir -Force | Out-Null
$target = 'D:\Jade\control'
New-Item -ItemType Directory -Path $target -Force | Out-Null
$config = [ordered]@{
    repo = $repo
    secrets_file = (Resolve-Path -LiteralPath $SecretsFile).Path
    private_dir = (Resolve-Path -LiteralPath $PrivateDir).Path
}
$configPath = Join-Path $target 'control.json'
$config | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $configPath -Encoding UTF8

# Manual double-click startup: pythonw.exe has no visible console.
$vbs = @'
Option Explicit
Dim shell, fs, app, root, config
Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
app = fs.GetParentFolderName(WScript.ScriptFullName)
root = "__REPO__"
config = app & "\control.json"
shell.CurrentDirectory = root
shell.Run Chr(34) & "__PYTHONW__" & Chr(34) & " -m src.jade_runtime.remote_control --config " & Chr(34) & config & Chr(34), 0, False
'@
$vbs = $vbs.Replace('__REPO__', $repo).Replace('__PYTHONW__', $PythonW)
$vbsPath = Join-Path $target 'Jade-Control.vbs'
$vbs | Set-Content -LiteralPath $vbsPath -Encoding ASCII

# One persistent per-user task, launched when the owner signs in to Windows.
# It never launches Jade itself; only the controller remains running.
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute $PythonW -Argument ('-m src.jade_runtime.remote_control --config "' + $configPath + '"') -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName 'Jade Remote Control' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null

$desktop = [Environment]::GetFolderPath('Desktop')
$link = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desktop 'Jade Control.lnk'))
$link.TargetPath = Join-Path $env:WINDIR 'System32\wscript.exe'
$link.Arguments = '"' + $vbsPath + '"'
$link.WorkingDirectory = $repo
$link.Description = 'Lancer le contrôleur de Jade sans fenêtre'
$link.Save()

Start-ScheduledTask -TaskName 'Jade Remote Control'
Start-Sleep -Seconds 2
$task = Get-ScheduledTask -TaskName 'Jade Remote Control'
Write-Host ('Tâche automatique installée : Jade Remote Control (' + $task.State + ')')
Write-Host "Raccourci bureau créé : Jade Control.lnk"
Write-Host "Contrôleur : 127.0.0.1:8771. PyCharm Run doit être lancé séparément."
Write-Host "Le fichier control.json contient uniquement des chemins, aucun jeton."
Write-Host "Pour la route mobile, vérifier Tailscale Serve puis ajouter /control vers 127.0.0.1:8771."
