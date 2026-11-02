[CmdletBinding()]
param(
    [string]$SourceCmo3,
    [string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
if (-not $SourceCmo3) {
    $SourceCmo3 = Join-Path $workspace 'reports\Jade_rig_5_2_v003.TEST_eye_lr_mouth_head_xyz_body_breath_hair_front_back_secondary_atlas_r02_zorder.cmo3'
}
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $workspace 'reports\vtube_studio\Jade'
}

$cubism = 'C:\Program Files\Live2D Cubism 5.2'
$app = Join-Path $cubism 'app'
$java = Join-Path $app 'jre\bin\java.exe'
$javac = 'C:\Program Files\Microsoft\jdk-11.0.12.7-hotspot\bin\javac.exe'
$build = Join-Path $PSScriptRoot '.cubism-runtime-export-build'
$classPath = "$build;$app\lib\*;$app\lib\jogl\*"
$nativePath = "$app\dll64;$app\dll64\windows-amd64"

New-Item -ItemType Directory -Force -Path $build, $OutputDirectory | Out-Null
$resolvedSourceCmo3 = [IO.Path]::GetFullPath($SourceCmo3)
$resolvedOutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
if (-not (Test-Path -LiteralPath $resolvedSourceCmo3 -PathType Leaf)) {
    throw "Source CMO3 not found: $resolvedSourceCmo3"
}
& $javac -encoding UTF-8 -d $build (Join-Path $PSScriptRoot 'CubismExportRunner.java')
if ($LASTEXITCODE -ne 0) { throw "runner compilation failed: $LASTEXITCODE" }

$previousPath = $env:PATH
try {
    $env:PATH = "$env:PATH;$app\dll64"
    Push-Location $cubism
    try {
        & $java -classpath $classPath "-Djava.library.path=$nativePath" `
            '-Djogamp.gluegen.UseTempJarCache=false' '-Dsun.java2d.d3d=false' `
            '-Duser.language=en' '-XX:MaxRAMPercentage=100' '-Djava.locale.providers=COMPAT,SPI' `
            jade.export.CubismExportRunner $resolvedSourceCmo3 $resolvedOutputDirectory
        if ($LASTEXITCODE -ne 0) { throw "Cubism Runtime export failed: $LASTEXITCODE" }
    } finally {
        Pop-Location
    }
} finally {
    $env:PATH = $previousPath
}
