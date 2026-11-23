# Install the private controller for the signed-in Windows user; no admin rights.
[CmdletBinding()]
param(
    [string] $PrivateDir = 'D:\Codex\private\jade-runtime',
    [string] $SecretsFile = 'D:\Codex\private\jade-20261102\jade-actif-20261103.env',
    [string] $PythonExe = '',
    [switch] $SkipTailscale
)
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'Windows uniquement.' }
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if (-not (Test-Path (Join-Path $repo 'tools\jade_pycharm_runner.py'))) { throw 'Depot Jade introuvable.' }
if (-not (Test-Path -LiteralPath $SecretsFile -PathType Leaf)) { throw "Fichier prive absent : $SecretsFile" }
$privatePath = [IO.Path]::GetFullPath($PrivateDir)
$runDir = Join-Path $privatePath 'control'
New-Item -ItemType Directory -Path $runDir -Force | Out-Null
if (-not $PythonExe) {
    foreach ($candidate in @(
        'D:\Codex\caches\venvs\jade-runtime-d-20261114\Scripts\pythonw.exe',
        (Join-Path $repo '.venv\Scripts\pythonw.exe')
    )) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { $PythonExe = $candidate; break }
    }
    if (-not $PythonExe) {
        $cmd = Get-Command pythonw.exe -ErrorAction SilentlyContinue
        if ($cmd) { $PythonExe = $cmd.Source }
    }
}
if (-not $PythonExe -or -not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    throw 'Pythonw du venv Jade introuvable ; preciser -PythonExe.'
}
$configPath = Join-Path $runDir 'config.json'
@{ repo = $repo; secrets_file = [IO.Path]::GetFullPath($SecretsFile); private_dir = $privatePath } |
    ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $configPath -Encoding UTF8

$taskName = 'Jade - Controle distant PyCharm'
$user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$argument = '-m src.jade_runtime.remote_control --config "' + $configPath + '"'
$action = New-ScheduledTaskAction -Execute $PythonExe -Argument $argument -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null

# The shortcut runs an existing scheduled task; the console never stays open.
$launcher = Join-Path $runDir 'Lancer-Controle-Jade.vbs'
@'
Set shell = CreateObject("WScript.Shell")
shell.Run "schtasks.exe /run /tn ""Jade - Controle distant PyCharm""", 0, False
'@ | Set-Content -LiteralPath $launcher -Encoding ASCII
$shortcut = Join-Path $runDir 'Lancer-Controle-Jade.lnk'
$wsh = New-Object -ComObject WScript.Shell
$link = $wsh.CreateShortcut($shortcut)
$link.TargetPath = "$env:WINDIR\System32\wscript.exe"
$link.Arguments = '"' + $launcher + '"'
$link.WorkingDirectory = $runDir
$link.WindowStyle = 7
$link.Description = 'Controle Jade en arriere-plan'
$link.Save()
Start-ScheduledTask -TaskName $taskName
Write-Host "Controleur installe : $taskName"
Write-Host "Raccourci manuel : $shortcut"
Write-Host "Configuration : $configPath"

if (-not $SkipTailscale) {
    $tailscale = Get-Command tailscale.exe -ErrorAction SilentlyContinue
    $tailscaleExe = if ($tailscale) { $tailscale.Source } else { 'D:\Codex\tools\Tailscale\tailscale.exe' }
    if (Test-Path -LiteralPath $tailscaleExe) {
        # Private Serve path only; existing / (Jade 8766) is preserved.
        & $tailscaleExe serve --bg --set-path=/control 8771
        if ($LASTEXITCODE -ne 0) { Write-Warning 'Configurer Tailscale Serve /control manuellement.' }
        else { Write-Host 'Tailscale Serve : /control -> port local 8771' }
    } else {
        Write-Warning 'Tailscale introuvable : configurer Serve /control manuellement.'
    }
}
