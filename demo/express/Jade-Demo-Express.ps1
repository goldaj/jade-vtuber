# Jade Demo Express: Windows PowerShell 5.1 / WinForms. Offline simulation only.
param([switch]$SelfTest)
$ErrorActionPreference = 'Stop'
function Reply-Demo([string]$message) {
    $value = $message.Trim().ToLowerInvariant()
    if (-not $value) { return '' }
    if ($value -match 'bonjour|salut|hello|coucou') {
        return 'Salut ! Je suis une simulation locale de Jade, sans intelligence artificielle ni appel reseau.'
    }
    if ($value -match 'qui es.tu|ton nom|presentation') {
        return 'Je suis la demo Express de Jade. Le vrai moteur conversationnel se lance separement.'
    }
    if ($value -match 'discord|twitch|mobile|telephone|micro|voix') {
        return 'Ces fonctions existent dans le projet complet selon la branche. Cette demo ne contacte aucun service.'
    }
    if ($value -match 'avatar|live2d|modele|anime') {
        return 'Le Live2D anime demande son modele et ses dependances. Ce portrait de demo est dessine localement.'
    }
    if ($value -match 'aide|comment|fonction') {
        return 'Essaie : Bonjour, Qui es-tu ?, Discord, Avatar. Les guides sont dans docs/handbook du depot.'
    }
    return 'Message recu. Cette reponse est une simulation deterministe, et non une reponse generee par IA.'
}
if ($SelfTest) {
    if ((Reply-Demo 'Bonjour') -notmatch 'simulation') { throw 'demo greeting test failed' }
    if ((Reply-Demo 'Discord') -notmatch 'aucun service') { throw 'demo services test failed' }
    if (-not (Reply-Demo 'test')) { throw 'demo fallback test failed' }
    Write-Host 'Jade Demo Express: offline checks OK'
    exit 0
}
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()
$form = New-Object System.Windows.Forms.Form
$form.Text = 'Jade | Demo Express hors ligne'
$form.ClientSize = New-Object System.Drawing.Size(750, 650)
$form.MinimumSize = New-Object System.Drawing.Size(620, 580)
$form.StartPosition = 'CenterScreen'
$form.Font = New-Object System.Drawing.Font('Segoe UI', 10)
$form.BackColor = [System.Drawing.Color]::FromArgb(25,26,42)
$form.ForeColor = [System.Drawing.Color]::White

$header = New-Object System.Windows.Forms.Label
$header.Text = 'JADE  |  DEMO EXPRESS'
$header.Font = New-Object System.Drawing.Font('Segoe UI Semibold', 17)
$header.ForeColor = [System.Drawing.Color]::FromArgb(191,179,245)
$header.Location = New-Object System.Drawing.Point(24,16)
$header.Size = New-Object System.Drawing.Size(700,38)
$form.Controls.Add($header)

$portrait = New-Object System.Windows.Forms.Panel
$portrait.Location = New-Object System.Drawing.Point(24,64)
$portrait.Size = New-Object System.Drawing.Size(700,150)
$portrait.Anchor = 'Top,Left,Right'
$portrait.BackColor = [System.Drawing.Color]::FromArgb(42,39,64)
$portrait.Add_Paint({
    param($sender,$event)
    $g = $event.Graphics
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $pen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(194,173,246), 4)
    $face = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(238,209,219))
    $hair = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(103,79,127))
    $dark = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(60,43,72))
    $x = [int](($sender.ClientSize.Width - 126)/2)
    $g.FillEllipse($hair,$x,8,126,132)
    $g.FillEllipse($face,$x+10,18,106,119)
    $g.FillEllipse($hair,$x+3,8,117,39)
    $g.FillEllipse($dark,$x+39,76,8,11)
    $g.FillEllipse($dark,$x+82,76,8,11)
    $g.DrawArc($pen,$x+44,88,48,30,22,130)
    $pen.Dispose();$face.Dispose();$hair.Dispose();$dark.Dispose()
})
$form.Controls.Add($portrait)

$disclaimer = New-Object System.Windows.Forms.Label
$disclaimer.Text = 'Prototype visuel + reponses simulees. Aucun compte, micro, cle API, reseau ou SDK requis.'
$disclaimer.Location = New-Object System.Drawing.Point(24,220)
$disclaimer.Size = New-Object System.Drawing.Size(700,38)
$disclaimer.ForeColor = [System.Drawing.Color]::FromArgb(204,201,221)
$disclaimer.Anchor = 'Top,Left,Right'
$form.Controls.Add($disclaimer)

$chat = New-Object System.Windows.Forms.TextBox
$chat.ReadOnly = $true
$chat.Multiline = $true
$chat.ScrollBars = 'Vertical'
$chat.BackColor = [System.Drawing.Color]::FromArgb(34,35,55)
$chat.ForeColor = [System.Drawing.Color]::White
$chat.Font = New-Object System.Drawing.Font('Segoe UI', 10)
$chat.Location = New-Object System.Drawing.Point(24,269)
$chat.Size = New-Object System.Drawing.Size(700,254)
$chat.Anchor = 'Top,Bottom,Left,Right'
$form.Controls.Add($chat)

$input = New-Object System.Windows.Forms.TextBox
$input.Location = New-Object System.Drawing.Point(24,540)
$input.Size = New-Object System.Drawing.Size(550,28)
$input.Anchor = 'Bottom,Left,Right'
$form.Controls.Add($input)
$send = New-Object System.Windows.Forms.Button
$send.Text = 'Envoyer'
$send.Location = New-Object System.Drawing.Point(585,538)
$send.Size = New-Object System.Drawing.Size(139,32)
$send.Anchor = 'Bottom,Right'
$send.BackColor = [System.Drawing.Color]::FromArgb(182,157,244)
$send.ForeColor = [System.Drawing.Color]::Black
$form.Controls.Add($send)
$hint = New-Object System.Windows.Forms.Label
$hint.Text = 'Exemples : Bonjour   |   Qui es-tu ?   |   Discord   |   Avatar   |   Aide'
$hint.Location = New-Object System.Drawing.Point(24,590)
$hint.Size = New-Object System.Drawing.Size(700,30)
$hint.Anchor = 'Bottom,Left,Right'
$form.Controls.Add($hint)
$newline = [Environment]::NewLine
$chat.AppendText("JADE [DEMO] : Bienvenue. Je fonctionne hors ligne avec des reponses pre-ecrites.$newline$newline")
$send.Add_Click({
    $value = $input.Text.Trim()
    if (-not $value) { return }
    if ($value.Length -gt 1200) {
        [System.Windows.Forms.MessageBox]::Show('1200 caracteres maximum') | Out-Null
        return
    }
    $chat.AppendText("VOUS : $value$newline")
    $response = Reply-Demo $value
    $chat.AppendText("JADE [DEMO] : $response$newline$newline")
    $input.Clear();$input.Focus()
})
$input.Add_KeyDown({
    param($sender,$event)
    if ($event.KeyCode -eq [System.Windows.Forms.Keys]::Enter) {
        $event.SuppressKeyPress = $true
        $send.PerformClick()
    }
})
[void]$form.ShowDialog()
