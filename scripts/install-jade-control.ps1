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
$taskInstalled = $false
try {
    Register-ScheduledTask -TaskName 'Jade Remote Control' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
    $taskInstalled = $true
} catch {
    Write-Warning ('Tâche Windows non installée : ' + $_.Exception.Message)
    Write-Warning 'Réexécuter le programme avec les droits nécessaires. Le raccourci manuel sera créé.'
}

# Prefer the scheduled task: multiple manual clicks never spawn new controllers.
if ($taskInstalled) {
    @'
Option Explicit
Dim shell
Set shell = CreateObject("WScript.Shell")
shell.Run "schtasks.exe /run /tn ""Jade Remote Control""", 0, False
'@ | Set-Content -LiteralPath $vbsPath -Encoding ASCII
}

$desktop = [Environment]::GetFolderPath('Desktop')
$link = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desktop 'Jade Control.lnk'))
$link.TargetPath = Join-Path $env:WINDIR 'System32\wscript.exe'
$link.Arguments = '"' + $vbsPath + '"'
$link.WorkingDirectory = $repo
$link.Description = 'Lancer le contrôleur de Jade sans fenêtre'
$link.Save()

if ($taskInstalled) {
    try {
        Start-ScheduledTask -TaskName 'Jade Remote Control'
        Start-Sleep -Seconds 2
        $task = Get-ScheduledTask -TaskName 'Jade Remote Control'
        Write-Host ('Tâche automatique installée : Jade Remote Control (' + $task.State + ')')
    } catch {
        Write-Warning ('Tâche installée mais lancement à vérifier : ' + $_.Exception.Message)
    }
}
Write-Host "Raccourci bureau créé : Jade Control.lnk"
Write-Host "Contrôleur : 127.0.0.1:8771. PyCharm Run doit être lancé séparément."
Write-Host "Le fichier control.json contient uniquement des chemins, aucun jeton."
# Preserve the existing root / -> Jade PWA route; add only /control.
# On Windows this operation may require an elevated terminal. Failure is
# reported, but does not undo the installed task and desktop shortcut.
$tailscale = Get-Command 'tailscale.exe' -ErrorAction SilentlyContinue
if (-not $tailscale) {
    $fallback = 'D:\Codex\tools\Tailscale\tailscale.exe'
    if (Test-Path -LiteralPath $fallback -PathType Leaf) {
        $tailscalePath = $fallback
    } else {
        $tailscalePath = $null
    }
} else {
    $tailscalePath = $tailscale.Source
}
if ($tailscalePath) {
    & $tailscalePath serve --bg --set-path=/control http://127.0.0.1:8771
    if ($LASTEXITCODE -eq 0) {
        Write-Host 'Tailscale Serve : /control ajouté sans modifier la route / existante.'
    } else {
        Write-Warning 'Tailscale Serve /control non configuré : exécuter la commande ci-dessus en terminal Windows administrateur.'
    }
} else {
    Write-Warning 'Tailscale CLI introuvable : /control reste à ajouter via tailscale serve.'
}

