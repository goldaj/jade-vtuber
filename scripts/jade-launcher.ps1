# Lanceur Windows personnel pour Jade. Fonctionne depuis D:\Jade\launcher.
# Aucun token n'est stocke ici ; seule l'adresse optionnelle du fichier prive est conservee.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$settingsPath = Join-Path $PSScriptRoot 'launcher.json'
if (-not (Test-Path -LiteralPath $settingsPath -PathType Leaf)) {
    [System.Windows.Forms.MessageBox]::Show('Configuration absente. Relancer Installer-Launcher-Jade.cmd depuis le depot.', 'Jade')
    return
}
$settings = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json
$script:repo = [string]$settings.repo
if (-not (Test-Path -LiteralPath (Join-Path $script:repo '.git'))) {
    [System.Windows.Forms.MessageBox]::Show('Depot Git Jade absent : ' + $script:repo, 'Jade')
    return
}
$null = Get-Command git -ErrorAction Stop

function Invoke-Local {
    param([string]$Tool, [string[]]$Arguments)
    Push-Location -LiteralPath $script:repo
    $old = $ErrorActionPreference
    try {
        # Windows PowerShell 5.1 peut convertir stderr natif en ErrorRecord.
        $ErrorActionPreference = 'Continue'
        $lines = & $Tool @Arguments 2>&1
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $old
        Pop-Location
    }
    $output = ($lines | ForEach-Object { [string]$_ }) -join [Environment]::NewLine
    if ($code -ne 0) {
        throw ('Echec ' + $Tool + ' (code ' + $code + ') : ' + $output)
    }
    return $output.Trim()
}
function Git {
    param([string[]]$Arguments)
    return Invoke-Local 'git' (@('-C', $script:repo) + $Arguments)
}

$form = New-Object System.Windows.Forms.Form
$form.Text = 'Jade | Launcher local'
$form.ClientSize = New-Object System.Drawing.Size(730, 465)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.Font = New-Object System.Drawing.Font('Segoe UI', 10)

function LabelAt([string]$name, [int]$x, [int]$y, [int]$width) {
    $label = New-Object System.Windows.Forms.Label
    $label.Text = $name
    $label.SetBounds($x, $y, $width, 24)
    $form.Controls.Add($label)
    return $label
}
function ButtonAt([string]$name, [int]$x, [int]$y, [int]$width) {
    $button = New-Object System.Windows.Forms.Button
    $button.Text = $name
    $button.SetBounds($x, $y, $width, 33)
    $form.Controls.Add($button)
    return $button
}

$null = LabelAt 'Branche Git a lancer' 22 20 310
$branchBox = New-Object System.Windows.Forms.ComboBox
$branchBox.DropDownStyle = 'DropDownList'
$branchBox.SetBounds(22, 45, 465, 32)
$form.Controls.Add($branchBox)
$refreshButton = ButtonAt 'Actualiser Git' 500 43 205

$null = LabelAt 'Configuration de demarrage' 22 92 350
$modeBox = New-Object System.Windows.Forms.ComboBox
$modeBox.DropDownStyle = 'DropDownList'
$modeBox.SetBounds(22, 118, 683, 32)
[void]$modeBox.Items.AddRange([object[]]@(
    'Discord vocal + texte + avatar',
    'Discord texte seulement',
    'Micro local + avatar',
    'Application mobile privee',
    'Discord vocal + avatar + mobile',
    'Demo hors ligne'
))
$modeBox.SelectedIndex = 0
$form.Controls.Add($modeBox)

$syncCheck = New-Object System.Windows.Forms.CheckBox
$syncCheck.Text = 'Installer / verifier les dependances Poetry (recommande)'
$syncCheck.SetBounds(22, 163, 600, 25)
$syncCheck.Checked = $true
$form.Controls.Add($syncCheck)
$lfsCheck = New-Object System.Windows.Forms.CheckBox
$lfsCheck.Text = 'Recuperer les fichiers Live2D (Git LFS) si necessaire'
$lfsCheck.SetBounds(22, 192, 600, 25)
$lfsCheck.Checked = $true
$form.Controls.Add($lfsCheck)

$null = LabelAt 'Chemin de configuration privee (facultatif, valeurs jamais affichees)' 22 227 660
$secretBox = New-Object System.Windows.Forms.TextBox
$secretBox.SetBounds(22, 254, 573, 28)
$secretBox.Text = [string]$settings.secretsFile
$form.Controls.Add($secretBox)
$browseButton = ButtonAt 'Parcourir...' 602 252 103
$browseButton.Add_Click({
    $picker = New-Object System.Windows.Forms.OpenFileDialog
    $picker.Filter = 'Fichiers de configuration (*.env;*.txt)|*.env;*.txt|Tous les fichiers (*.*)|*.*'
    if ($picker.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
        $secretBox.Text = $picker.FileName
    }
    $picker.Dispose()
})

$launchButton = ButtonAt 'Mettre a jour et lancer Jade' 22 308 683
$launchButton.Height = 44
$logBox = New-Object System.Windows.Forms.TextBox
$logBox.Multiline = $true
$logBox.ReadOnly = $true
$logBox.ScrollBars = 'Vertical'
$logBox.SetBounds(22, 361, 683, 81)
$form.Controls.Add($logBox)
function Info([string]$message) {
    $logBox.AppendText($message + [Environment]::NewLine)
    $logBox.SelectionStart = $logBox.TextLength
    $logBox.ScrollToCaret()
    $form.Refresh()
}

function Load-Branches {
    $current = Git @('branch', '--show-current')
    $refs = Git @('for-each-ref', '--format=%(refname:strip=3)', 'refs/remotes/origin')
    $branches = @($refs -split '\r?\n' | Where-Object { $_ -and $_ -ne 'HEAD' } | Sort-Object -Unique)
    $branchBox.Items.Clear()
    foreach ($branch in $branches) { [void]$branchBox.Items.Add($branch) }
    if ($branches -contains $current) { $branchBox.SelectedItem = $current }
    elseif ($branches -contains 'develop') { $branchBox.SelectedItem = 'develop' }
    elseif ($branches.Count -gt 0) { $branchBox.SelectedIndex = 0 }
    Info ('Branche locale : ' + $current + ' | ' + $branches.Count + ' branches distantes.')
}
$refreshButton.Add_Click({
    try {
        Info 'Synchronisation de la liste des branches...'
        [void](Git @('fetch', '--prune', 'origin'))
        Load-Branches
    } catch {
        [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Git')
        Info 'Actualisation impossible. Aucun changement de branche.'
    }
})

function Mode-Flags([string]$mode) {
    switch ($mode) {
        'Discord vocal + texte + avatar' { return @('--live','--discord','--voice','--discord-voice','--avatar') }
        'Discord texte seulement'       { return @('--live','--discord') }
        'Micro local + avatar'           { return @('--live','--mic','--voice','--avatar') }
        'Application mobile privee'      { return @('--live','--mobile') }
        'Discord vocal + avatar + mobile' { return @('--live','--discord','--voice','--discord-voice','--avatar','--mobile') }
        'Demo hors ligne'                { return @() }
    }
    throw 'Profil de lancement inconnu.'
}
function Mode-Extras([string]$mode) {
    switch ($mode) {
        'Discord vocal + texte + avatar' { return @('-E','discord-voice','-E','avatar') }
        'Discord texte seulement'       { return @('-E','discord') }
        'Micro local + avatar'           { return @('-E','mic','-E','avatar') }
        'Application mobile privee'      { return @() }
        'Discord vocal + avatar + mobile' { return @('-E','discord-voice','-E','avatar') }
        'Demo hors ligne'                { return @() }
    }
    throw 'Profil de dependances inconnu.'
}
function Active-Jade {
    $marker = Join-Path $PSScriptRoot 'jade-active.pid'
    if (-not (Test-Path -LiteralPath $marker)) { return $false }
    $processId = 0
    if (-not [int]::TryParse((Get-Content -LiteralPath $marker -Raw).Trim(), [ref]$processId)) { return $false }
    return $null -ne (Get-Process -Id $processId -ErrorAction SilentlyContinue)
}
$launchButton.Add_Click({
    $launchButton.Enabled = $false
    try {
        if (Active-Jade) {
            throw 'Une console du launcher est deja ouverte. Fermer Jade avec Ctrl+C, puis la console avant de changer de branche.'
        }
        if ($branchBox.SelectedIndex -lt 0) { throw 'Aucune branche selectionnee. Actualiser Git.' }
        $branch = [string]$branchBox.SelectedItem
        $mode = [string]$modeBox.SelectedItem
        $flags = @(Mode-Flags $mode)
        [void](Get-Command poetry -ErrorAction Stop)
        $privatePath = $secretBox.Text.Trim()
        if ($privatePath -and -not (Test-Path -LiteralPath $privatePath -PathType Leaf)) {
            throw 'Fichier de configuration privee introuvable.'
        }
        Info ('Preparation de ' + $branch + '...')
        [void](Git @('fetch', '--prune', 'origin'))
        # Les branches proviennent de Git, jamais d'une saisie libre.
        $remoteRefs = @( (Git @('for-each-ref', '--format=%(refname:strip=3)', 'refs/remotes/origin')) -split '\r?\n' )
        if ($remoteRefs -notcontains $branch) { throw 'Branche distante introuvable.' }
        $dirty = Git @('status', '--porcelain')
        if ($dirty) { throw 'Fichiers locaux modifies ou non suivis : commit/stash manuel requis. Rien ne sera ecrase.' }
        $current = Git @('branch', '--show-current')
        if ($current -ne $branch) {
            $localRefs = @( (Git @('for-each-ref', '--format=%(refname:strip=2)', 'refs/heads')) -split '\r?\n' )
            if ($localRefs -contains $branch) {
                [void](Git @('switch', $branch))
            } else {
                [void](Git @('switch', '--track', '-c', $branch, ('origin/' + $branch)))
            }
        }
        [void](Git @('merge', '--ff-only', ('origin/' + $branch)))
        Info ('Branche mise a jour sans reinitialisation destructive : ' + $branch)
        if ($lfsCheck.Checked -and $mode -match 'avatar') {
            Info 'Recuperation des assets Live2D...'
            [void](Git @('lfs', 'pull'))
        }
        if ($syncCheck.Checked) {
            Info 'Verification des dependances Poetry...'
            $syncArgs = @('sync','--only','main') + @(Mode-Extras $mode)
            [void](Invoke-Local 'poetry' $syncArgs)
        }
        $previousSecrets = [Environment]::GetEnvironmentVariable('JADE_SECRETS_FILE','Process')
        try {
            if ($privatePath) { $env:JADE_SECRETS_FILE = $privatePath }
            Info 'Preflight local, sans connexion ni facturation...'
            $checks = Invoke-Local 'poetry' (@('run','python','main.py','--preflight') + $flags)
            Info ((($checks -split '\r?\n') | Select-Object -Last 2 | Out-String).Trim())
        } finally {
            [Environment]::SetEnvironmentVariable('JADE_SECRETS_FILE',$previousSecrets,'Process')
        }
        $settings.secretsFile = $privatePath
        $settings | ConvertTo-Json | Set-Content -LiteralPath $settingsPath -Encoding UTF8
        $runPath = Join-Path $PSScriptRoot 'jade-run.json'
        @{ repo = $script:repo; branch = $branch; mode = $mode; flags = $flags; secretsFile = $privatePath } |
            ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $runPath -Encoding UTF8
        $runner = Join-Path $PSScriptRoot 'JadeRunner.ps1'
        $start = Start-Process -FilePath 'powershell.exe' -WorkingDirectory $script:repo -ArgumentList @(
            '-NoLogo','-NoProfile','-ExecutionPolicy','Bypass','-File',('"' + $runner + '"'),
            '-RunConfig',('"' + $runPath + '"')
        ) -PassThru
        [string]$start.Id | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'jade-active.pid') -Encoding ASCII
        Info 'Console Jade lancee. Pour terminer : Ctrl+C dans sa console.'
        if ($mode -match 'mobile') {
            Info 'Mobile : verifier Tailscale Serve sur le PC. Le launcher ne change pas ses routes.'
        }
    } catch {
        Info ('ECHEC : ' + $_.Exception.Message)
        [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Jade - demarrage impossible')
    } finally {
        $launchButton.Enabled = $true
    }
})
try { Load-Branches } catch { Info ('Git non pret : ' + $_.Exception.Message) }
[void]$form.ShowDialog()
$form.Dispose()
