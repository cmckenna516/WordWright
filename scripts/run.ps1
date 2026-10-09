$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\pythonw.exe"
$localAppData = [Environment]::GetFolderPath("LocalApplicationData")
if ([string]::IsNullOrWhiteSpace($localAppData)) {
    $logPath = Join-Path $projectRoot "wordwright.log"
} else {
    $logPath = Join-Path $localAppData "Wordwright\logs\wordwright.log"
}
if (-not [string]::IsNullOrWhiteSpace($env:WORDWRIGHT_MODEL_DIR)) {
    $modelDirectory = $env:WORDWRIGHT_MODEL_DIR
} elseif ([string]::IsNullOrWhiteSpace($localAppData)) {
    $modelDirectory = Join-Path $projectRoot ".models"
} else {
    $modelDirectory = Join-Path $localAppData "Wordwright\models"
}

if (Test-Path -LiteralPath (Join-Path $projectRoot ".venv\Lib\site-packages\faster_whisper")) {
    $python = $venvPython
} else {
    throw "Wordwright is not set up. Double-click Setup Wordwright.cmd first."
}

Write-Host "Starting Wordwright..."
$process = Start-Process `
    -FilePath $python `
    -ArgumentList @("-m", "wordwright", "--model-dir", $modelDirectory) `
    -WorkingDirectory $projectRoot `
    -PassThru

Start-Sleep -Seconds 2
$process.Refresh()
if ($process.HasExited) {
    Write-Host ""
    Write-Host "Wordwright exited before its window could open." -ForegroundColor Red
    if (Test-Path -LiteralPath $logPath) {
        Write-Host "Recent diagnostic messages:"
        Get-Content -LiteralPath $logPath -Tail 20
    } else {
        Write-Host "No diagnostic log was created."
    }
    throw "Wordwright did not start successfully."
}

Write-Host "Wordwright started (process $($process.Id)). Its launcher should now be visible."

