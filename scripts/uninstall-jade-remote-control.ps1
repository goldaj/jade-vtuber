# Remove the controller's automatic startup without touching Jade's private data.
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'Windows uniquement.' }
$taskName = 'Jade - Controle distant PyCharm'
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($task) {
    if ($task.State -eq 'Running') { Stop-ScheduledTask -TaskName $taskName }
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}
Write-Host 'Demarrage automatique et controleur Windows desinstalles.'
Write-Host 'Les fichiers de logs, les secrets et le profil PyCharm sont conserves.'
Write-Host 'Pour retirer /control de Tailscale Serve, utiliser la commande correspondant a la version de Tailscale installee, apres inspection de tailscale serve status.'
