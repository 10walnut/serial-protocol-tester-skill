param(
    [switch]$SkipInstall,
    [switch]$OneDir,
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppDir = Join-Path $RepoRoot "serial-protocol-tester\assets\pyside6-serial-console"
$VenvDir = Join-Path $AppDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$Requirements = Join-Path $AppDir "requirements.txt"
$App = Join-Path $AppDir "serial_console.py"
$SampleProtocol = Join-Path $AppDir "sample_protocol.json"
$BuildRoot = Join-Path $RepoRoot "build"
$DistRoot = Join-Path $RepoRoot "dist"
$SpecRoot = Join-Path $BuildRoot "pyinstaller-spec"
$WorkRoot = Join-Path $BuildRoot "pyinstaller-work"
$AppName = "SerialProtocolTester"

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
if (-not (Test-Path $SampleProtocol)) {
    throw "Sample protocol not found: $SampleProtocol"
}

if (-not (Test-Path $VenvPython)) {
    Invoke-Step "Create virtual environment" {
        & $Python -m venv $VenvDir
    }
}

if (-not $SkipInstall) {
    Invoke-Step "Install build dependencies" {
        & $VenvPython -m pip install --upgrade pip
        & $VenvPython -m pip install -r $Requirements
        & $VenvPython -m pip install pyinstaller
    }
}

New-Item -ItemType Directory -Force -Path $BuildRoot, $DistRoot, $SpecRoot, $WorkRoot | Out-Null

$ModeArgs = if ($OneDir) { @("--onedir") } else { @("--onefile") }
$Separator = if ($IsWindows -or $env:OS -eq "Windows_NT") { ";" } else { ":" }
$AddData = "$SampleProtocol$Separator."

Invoke-Step "Build $AppName" {
    Push-Location $AppDir
    try {
        & $VenvPython -m PyInstaller `
            --noconfirm `
            --clean `
            --windowed `
            @ModeArgs `
            --name $AppName `
            --distpath $DistRoot `
            --workpath $WorkRoot `
            --specpath $SpecRoot `
            --collect-submodules serial `
            --add-data $AddData `
            $App
    }
    finally {
        Pop-Location
    }
}

if ($OneDir) {
    $Output = Join-Path $DistRoot $AppName
}
else {
    $Output = Join-Path $DistRoot "$AppName.exe"
}

Write-Host ""
Write-Host "Build complete: $Output"
