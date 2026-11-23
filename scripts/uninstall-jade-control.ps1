# Remove the Windows task and manual shortcut; keep secrets, Git and logs.
$ErrorActionPreference = 'Stop'
$taskName = 'Jade Remote Control'
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($task) {
    if ($task.State -eq 'Running') { Stop-ScheduledTask -TaskName $taskName }
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}
$shortcut = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Jade Control.lnk'
if (Test-Path -LiteralPath $shortcut) { Remove-Item -LiteralPath $shortcut -Force }
Write-Host 'Controleur distant desinstalle. La configuration privee et les journaux sont conserves.'
Write-Host 'Verifier tailscale serve status et retirer la route /control si elle est devenue inutile.'
