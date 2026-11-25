[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = (Get-Item -LiteralPath $PSScriptRoot).FullName
$prefix = $root + [IO.Path]::DirectorySeparatorChar
$catalog = Join-Path $root 'SHA256SUMS.txt'
$entries = @(Get-Content -LiteralPath $catalog -Encoding UTF8)
$seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
if ($entries.Count -eq 0) { throw 'Catalogue vide.' }

foreach ($entry in $entries) {
    if ($entry -notmatch '^([a-f0-9]{64})  (.+)$') {
        throw "Ligne de catalogue invalide : $entry"
    }
    $expected = $Matches[1]
    $relative = $Matches[2]
    $file = [IO.Path]::GetFullPath((Join-Path $root $relative))
    if (!$file.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase) -or !$seen.Add($file)) {
        throw "Chemin hors livraison ou présent deux fois : $relative"
    }
    $actual = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash
    if ($actual -ne $expected) { throw "Empreinte incorrecte : $relative" }
}

foreach ($file in Get-ChildItem -LiteralPath $root -File -Recurse -Force) {
    if ($file.FullName -ne $catalog -and !$seen.Contains($file.FullName)) {
        throw "Fichier absent du catalogue : $($file.FullName)"
    }
}
Write-Output "$($seen.Count) fichiers vérifiés."
