param(
    [switch]$SkipInstall,
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppDir = Join-Path $RepoRoot "serial-protocol-tester\assets\pyside6-serial-console"
$VenvDir = Join-Path $AppDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$Requirements = Join-Path $AppDir "requirements.txt"
$App = Join-Path $AppDir "serial_console.py"

function Invoke-Step {
    param(
        [string]$Title,
        [scriptblock]$Action
    )
    Write-Host "==> $Title"
    & $Action
}

if (-not (Test-Path $App)) {
    throw "Serial console entry not found: $App"
}

if (-not (Test-Path $VenvPython)) {
    Invoke-Step "Create virtual environment" {
        & $Python -m venv $VenvDir
    }
}

if (-not $SkipInstall) {
    Invoke-Step "Install runtime dependencies" {
        & $VenvPython -m pip install --upgrade pip
        & $VenvPython -m pip install -r $Requirements
    }
}

Invoke-Step "Start Serial Protocol Tester" {
    Push-Location $AppDir
    try {
        & $VenvPython $App
    }
    finally {
        Pop-Location
    }
}
