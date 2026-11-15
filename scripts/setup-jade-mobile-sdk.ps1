# Installation locale des dependances Web Live2D deja obtenues legalement.
# Ne telecharge ni ne commit le SDK proprietaire et ne modifie aucun service VPS.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$PixiJs,
    [Parameter(Mandatory = $true)][string]$CubismCoreJs,
    [Parameter(Mandatory = $true)][string]$CubismAdapterJs,
    [string]$Destination = 'D:\Jade\private\mobile-sdk'
)
$ErrorActionPreference = 'Stop'
$mapping = @{
    'pixi.min.js' = $PixiJs
    'live2dcubismcore.min.js' = $CubismCoreJs
    'cubism4.min.js' = $CubismAdapterJs
}
$target = [System.IO.Path]::GetFullPath($Destination)
if (-not $target.StartsWith('D:\', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Le SDK du client Jade doit rester sur le disque D: du PC Jade.'
}
if (Test-Path -LiteralPath $target) {
    $existing = Get-ChildItem -LiteralPath $target -Force
    if ($existing.Count -gt 0) {
        throw 'Repertoire destination non vide : ne rien remplacer sans verification.'
    }
} else {
    New-Item -ItemType Directory -Path $target -Force | Out-Null
}
foreach ($name in @('pixi.min.js', 'live2dcubismcore.min.js', 'cubism4.min.js')) {
    $source = [System.IO.Path]::GetFullPath($mapping[$name])
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "Fichier absent : $name"
    }
    $file = Get-Item -LiteralPath $source
    if ($file.Length -le 1000 -or $file.Length -gt 20MB) {
        throw "Taille suspecte pour $name, verifier le vrai package SDK."
    }
    Copy-Item -LiteralPath $source -Destination (Join-Path $target $name)
}
Write-Host "SDK Web local pret dans $target"
Get-ChildItem -LiteralPath $target -File | ForEach-Object {
    Write-Host "$($_.Name): $((Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash)"
}
Write-Host 'Renseigner JADE_MOBILE_VENDOR_DIR dans la configuration privee.'
