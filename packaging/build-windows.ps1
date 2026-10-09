param(
    [string]$Version = "0.1.0",
    [string]$Publisher = "Charlie McKenna",
    [string]$Python,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$buildEnvironment = Join-Path $projectRoot ".packaging-venv"
$buildPython = Join-Path $buildEnvironment "Scripts\python.exe"
$iconSource = Join-Path $projectRoot "src\wordwright\assets\logo-scroll-v2.png"
$iconDestination = Join-Path $PSScriptRoot "assets\wordwright.ico"
$specPath = Join-Path $PSScriptRoot "wordwright.spec"

if (-not $Python) {
    $systemPython = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($systemPython) {
        $Python = $systemPython.Source
    } else {
        throw "Python 3.11 or 3.12 is required to build the Windows package."
    }
}

function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Build command failed with exit code $LASTEXITCODE."
    }
}

if (-not (Test-Path -LiteralPath $buildPython)) {
    Invoke-Checked $Python @("-m", "venv", $buildEnvironment)
}

Invoke-Checked $buildPython @("-m", "pip", "install", "--upgrade", "pip")
Invoke-Checked $buildPython @("-m", "pip", "install", "--upgrade", "-e", $projectRoot, "pyinstaller>=6.15,<7")
Invoke-Checked $buildPython @(
    (Join-Path $PSScriptRoot "make_icon.py"),
    $iconSource,
    $iconDestination
)
Invoke-Checked $buildPython @("-m", "PyInstaller", "--noconfirm", "--clean", $specPath)

$executable = Join-Path $projectRoot "dist\Wordwright\Wordwright.exe"
if (-not (Test-Path -LiteralPath $executable)) {
    throw "PyInstaller completed without creating $executable"
}
Write-Host "Packaged application: $executable" -ForegroundColor Green

if ($SkipInstaller) {
    return
}

$isccCandidates = @(
    (Join-Path $env:USERPROFILE "AppData\Local\Programs\Inno Setup 6\ISCC.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
    (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
)
$iscc = $isccCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
if (-not $iscc) {
    $isccCommand = Get-Command iscc.exe -ErrorAction SilentlyContinue
    if ($isccCommand) {
        $iscc = $isccCommand.Source
    }
}
if (-not $iscc) {
    throw "Inno Setup 6 was not found. Install it, then rerun this build script."
}

Invoke-Checked $iscc @(
    "/DMyAppVersion=$Version",
    "/DMyAppPublisher=$Publisher",
    (Join-Path $PSScriptRoot "installer.iss")
)

$installer = Join-Path $projectRoot "release\Wordwright-Setup-$Version.exe"
if (-not (Test-Path -LiteralPath $installer)) {
    throw "Inno Setup completed without creating $installer"
}
Write-Host "Windows installer: $installer" -ForegroundColor Green

