# Builds dist\OcrRegionCapture.exe.
# Usage (PowerShell, in this folder):  .\build_exe.ps1
# Creates .venv if needed, installs packages, runs the tests, builds the exe.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (Get-Process OcrRegionCapture -ErrorAction SilentlyContinue) {
    throw "OcrRegionCapture.exe is running. Close it first (Windows locks a running exe)."
}

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

& $python -m pip install --quiet --upgrade pip
& $python -m pip install --quiet -r requirements-dev.txt

Write-Host "Running tests..."
& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed - exe not built." }

Write-Host "Building exe..."
& $python -m PyInstaller --noconfirm --clean OcrRegionCapture.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }

Write-Host ""
Write-Host "Done: $PSScriptRoot\dist\OcrRegionCapture.exe"
Write-Host "settings.json is created next to the exe on first start."
