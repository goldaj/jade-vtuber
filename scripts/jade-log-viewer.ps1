param(
    [string] $LogPath = 'D:\Codex\private\jade-runtime\logs\jade-pycharm-diagnostics.log'
)

# Separate, read-only console. It remains open after Jade exits so a crash can
# be read, and can be closed independently without stopping the runtime.
$ErrorActionPreference = 'Stop'
$Host.UI.RawUI.WindowTitle = 'Jade - journal technique'
Write-Host 'Journal technique Jade. Fermer cette fenetre ne ferme pas Jade.'
Write-Host 'En attente du journal si le fichier n existe pas encore.'
Write-Host ''

$offset = [long]0
$creation = $null
$decoder = [Text.Encoding]::UTF8.GetDecoder()
$bytes = New-Object byte[] 8192
$chars = New-Object char[] 8192
while ($true) {
    try {
        $info = Get-Item -LiteralPath $LogPath -ErrorAction Stop
        if ($null -eq $creation -or $info.CreationTimeUtc.Ticks -ne $creation -or $info.Length -lt $offset) {
            $offset = 0
            $creation = $info.CreationTimeUtc.Ticks
            $decoder = [Text.Encoding]::UTF8.GetDecoder()
        }
        $stream = [IO.File]::Open($LogPath, [IO.FileMode]::Open, [IO.FileAccess]::Read,
            ([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
        try {
            [void]$stream.Seek($offset, [IO.SeekOrigin]::Begin)
            while (($read = $stream.Read($bytes, 0, $bytes.Length)) -gt 0) {
                $count = $decoder.GetChars($bytes, 0, $read, $chars, 0, $false)
                if ($count -gt 0) { [Console]::Write($chars, 0, $count) }
            }
            $offset = $stream.Position
        } finally {
            $stream.Dispose()
        }
    } catch [System.IO.IOException] {
        # Rotation and concurrent writes are transient; try again next tick.
    } catch [System.Management.Automation.ItemNotFoundException] {
        # Jade can start after the viewer or rotate its file between reads.
        $creation = $null
        $offset = 0
        $decoder = [Text.Encoding]::UTF8.GetDecoder()
    }
    Start-Sleep -Milliseconds 300
}
