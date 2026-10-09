$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (Test-Path -LiteralPath (Join-Path $projectRoot ".venv\Lib\site-packages\faster_whisper")) {
    $python = $venvPython
} else {
    throw "Wordwright is not set up. Run scripts\setup.ps1 first."
}

& $python -m wordwright --debug --model-dir "$projectRoot\.models"

