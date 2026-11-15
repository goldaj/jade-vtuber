param([Parameter(Mandatory = $true)][string] $RunConfig)
$ErrorActionPreference = 'Stop'
try {
    $config = Get-Content -LiteralPath $RunConfig -Raw | ConvertFrom-Json
    if (-not (Test-Path -LiteralPath (Join-Path $config.repo 'main.py'))) {
        throw 'Depot Jade introuvable.'
    }
    if ($config.secretsFile) {
        if (-not (Test-Path -LiteralPath $config.secretsFile -PathType Leaf)) {
            throw 'Fichier de configuration privee introuvable.'
        }
        $env:JADE_SECRETS_FILE = [string]$config.secretsFile
    }
    Set-Location -LiteralPath $config.repo
    $flags = @($config.flags | ForEach-Object { [string]$_ })
    Write-Host ('Jade - branche : ' + $config.branch)
    Write-Host 'Canaux : tous les supports configures, sans priorite fixe.'
    Write-Host 'La console affiche les logs de Jade. Ctrl+C pour arreter proprement.'
    Write-Host ''
    & poetry run python main.py @flags
    $exitCode = $LASTEXITCODE
    Write-Host ''
    Write-Host ('Jade terminee (code ' + $exitCode + ').')
} catch {
    Write-Host ('Erreur de demarrage : ' + $_.Exception.Message) -ForegroundColor Red
}
Read-Host 'Appuyer sur Entree pour fermer cette fenetre'
