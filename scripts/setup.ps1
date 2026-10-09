param(
    [string]$Python
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvRoot = Join-Path $projectRoot ".venv"
$venvPython = Join-Path $venvRoot "Scripts\python.exe"
$setupCompleteMarker = Join-Path $projectRoot ".setup-complete"
$pipTemp = Join-Path $projectRoot ".pip-temp"
$localAppData = [Environment]::GetFolderPath("LocalApplicationData")
if (-not [string]::IsNullOrWhiteSpace($env:WORDWRIGHT_MODEL_DIR)) {
    $modelDirectory = $env:WORDWRIGHT_MODEL_DIR
} elseif ([string]::IsNullOrWhiteSpace($localAppData)) {
    $modelDirectory = Join-Path $projectRoot ".models"
} else {
    $modelDirectory = Join-Path $localAppData "Wordwright\models"
}
$verificationAudio = Join-Path $pipTemp "wordwright-functional-check.wav"
New-Item -ItemType Directory -Path $pipTemp -Force | Out-Null
Remove-Item -LiteralPath $setupCompleteMarker -Force -ErrorAction SilentlyContinue
$env:TEMP = $pipTemp
$env:TMP = $pipTemp

function Invoke-Checked {
    param(
        [string]$Executable,
        [string[]]$Arguments
    )

    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "A setup command failed with exit code $LASTEXITCODE."
    }
}

function Resolve-PythonCommand {
    param([string]$RequestedPython)

    if ($RequestedPython) {
        if (Test-Path -LiteralPath $RequestedPython) {
            return (Resolve-Path -LiteralPath $RequestedPython).Path
        }
        $requested = Get-Command $RequestedPython -ErrorAction SilentlyContinue
        if ($requested) {
            return $requested.Source
        }
        throw "The requested Python executable '$RequestedPython' could not be found."
    }

    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    return $null
}

if (Test-Path -LiteralPath $venvPython) {
    Write-Host "Updating the existing Wordwright environment..."
    Invoke-Checked $venvPython @("-m", "pip", "install", "--upgrade", "pip")
    Invoke-Checked $venvPython @("-m", "pip", "install", "--upgrade", "-e", $projectRoot)
    Invoke-Checked $venvPython @("-c", "import faster_whisper, PIL, pystray, sounddevice; import wordwright")
    $installedPython = $venvPython
} else {
    $systemPython = Resolve-PythonCommand -RequestedPython $Python
    $pythonLauncher = Get-Command py.exe -ErrorAction SilentlyContinue

    if ($systemPython) {
        Write-Host "Creating a private Wordwright Python environment..."
        Invoke-Checked $systemPython @("-m", "venv", $venvRoot)
        Invoke-Checked $venvPython @("-m", "pip", "install", "--upgrade", "pip")
        Invoke-Checked $venvPython @("-m", "pip", "install", "-e", $projectRoot)
        Invoke-Checked $venvPython @("-c", "import faster_whisper, PIL, pystray, sounddevice; import wordwright")
        $installedPython = $venvPython
    } elseif ($pythonLauncher) {
        $previousErrorPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & $pythonLauncher.Source -3.12 -c "import sys" *> $null
        $launcherExitCode = $LASTEXITCODE
        $ErrorActionPreference = $previousErrorPreference
        if ($launcherExitCode -ne 0) {
            throw "The Windows Python launcher is installed, but Python 3.12 is not available."
        }
        Write-Host "Creating a private Wordwright Python environment..."
        Invoke-Checked $pythonLauncher.Source @("-3.12", "-m", "venv", $venvRoot)
        Invoke-Checked $venvPython @("-m", "pip", "install", "--upgrade", "pip")
        Invoke-Checked $venvPython @("-m", "pip", "install", "-e", $projectRoot)
        Invoke-Checked $venvPython @("-c", "import faster_whisper, PIL, pystray, sounddevice; import wordwright")
        $installedPython = $venvPython
    } else {
        throw @"
Python 3.11 or 3.12 could not be found.

Install Python from https://www.python.org/downloads/windows/ and select
'Add Python to PATH' in the installer. Then double-click Setup Wordwright.cmd again.
"@
    }
}

Write-Host "Preparing and checking the local speech model..."
try {
    Add-Type -AssemblyName System.Speech
    $voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
    try {
        $voice.SetOutputToWaveFile($verificationAudio)
        $voice.Speak("Wordwright verification is working correctly.")
        $voice.SetOutputToNull()
    } finally {
        $voice.Dispose()
    }
    Invoke-Checked $installedPython @(
        (Join-Path $PSScriptRoot "preflight.py"),
        "--model-dir", $modelDirectory,
        "--audio", $verificationAudio
    )
} finally {
    Remove-Item -LiteralPath $verificationAudio -Force -ErrorAction SilentlyContinue
}

Set-Content -LiteralPath $setupCompleteMarker -Value "ready" -Encoding ascii

Write-Host ""
Write-Host "Wordwright setup and functional checks are complete." -ForegroundColor Green
Write-Host "Close this window, then double-click Start Wordwright.cmd."

