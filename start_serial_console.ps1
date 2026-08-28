param(
    [switch]$SkipInstall,
    [switch]$ResetVenv,
    [switch]$CheckOnly,
    [string]$PythonPath = ""
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppDir = Join-Path $RepoRoot "serial-protocol-tester\assets\pyside6-serial-console"
$AppPath = Join-Path $AppDir "serial_console.py"
$RequirementsPath = Join-Path $AppDir "requirements.txt"
$VenvDir = Join-Path $AppDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$LogDir = Join-Path $RepoRoot "logs"
$LogPath = Join-Path $LogDir ("start-{0}.log" -f (Get-Date -Format "yyyyMMdd-HHmmss"))
$TranscriptStarted = $false

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$Description
    )
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE"
    }
}

function Test-PythonCandidate {
    param([string]$Executable, [string[]]$Arguments)
    try {
        & $Executable @Arguments -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" 2>$null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

function Resolve-Python {
    if ($PythonPath) {
        if (-not (Get-Command $PythonPath -ErrorAction SilentlyContinue)) {
            throw "Python executable not found: $PythonPath"
        }
        if (-not (Test-PythonCandidate $PythonPath @())) {
            throw "Python 3.10 or newer is required: $PythonPath"
        }
        return [PSCustomObject]@{ Executable = $PythonPath; Arguments = @() }
    }

    $Candidates = @(
        [PSCustomObject]@{ Executable = "py"; Arguments = @("-3.13") },
        [PSCustomObject]@{ Executable = "py"; Arguments = @("-3.12") },
        [PSCustomObject]@{ Executable = "py"; Arguments = @("-3.11") },
        [PSCustomObject]@{ Executable = "py"; Arguments = @("-3.10") },
        [PSCustomObject]@{ Executable = "python"; Arguments = @() }
    )
    foreach ($Candidate in $Candidates) {
        if ((Get-Command $Candidate.Executable -ErrorAction SilentlyContinue) -and
            (Test-PythonCandidate $Candidate.Executable $Candidate.Arguments)) {
            return $Candidate
        }
    }
    throw "Python 3.10+ was not found. Install 64-bit Python from python.org and enable the Python launcher."
}

function Test-VenvModule {
    param([string]$ModuleName)
    if (-not (Test-Path -LiteralPath $VenvPython)) {
        return $false
    }
    & $VenvPython -c "import importlib.util, sys; raise SystemExit(0 if importlib.util.find_spec(sys.argv[1]) else 1)" $ModuleName
    return $LASTEXITCODE -eq 0
}

try {
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    try {
        Start-Transcript -LiteralPath $LogPath -Force | Out-Null
        $TranscriptStarted = $true
    }
    catch {
        Write-Warning "Could not start transcript logging: $($_.Exception.Message)"
    }

    Write-Host "Serial Protocol Tester" -ForegroundColor Cyan
    Write-Host "Workspace: $RepoRoot"

    if (-not (Test-Path -LiteralPath $AppPath)) {
        throw "Application entry point is missing: $AppPath"
    }
    if (-not (Test-Path -LiteralPath $RequirementsPath)) {
        throw "Requirements file is missing: $RequirementsPath"
    }

    if ($ResetVenv -and (Test-Path -LiteralPath $VenvDir)) {
        $ResolvedVenv = [System.IO.Path]::GetFullPath($VenvDir)
        $ResolvedAppDir = [System.IO.Path]::GetFullPath($AppDir)
        if (-not $ResolvedVenv.StartsWith($ResolvedAppDir, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove a virtual environment outside the application directory: $ResolvedVenv"
        }
        Write-Host "Removing old virtual environment: $ResolvedVenv"
        Remove-Item -LiteralPath $ResolvedVenv -Recurse -Force
    }

    if (-not (Test-Path -LiteralPath $VenvPython)) {
        $Python = Resolve-Python
        Write-Host "Creating virtual environment..."
        $CreateArgs = @($Python.Arguments) + @("-m", "venv", $VenvDir)
        Invoke-Checked $Python.Executable $CreateArgs "Virtual environment creation"
    }

    $MissingModules = @()
    if (-not (Test-VenvModule "PySide6")) { $MissingModules += "PySide6" }
    if (-not (Test-VenvModule "serial")) { $MissingModules += "pyserial" }

    if ($MissingModules.Count -gt 0) {
        if ($SkipInstall) {
            throw "Missing dependencies: $($MissingModules -join ', '). Run again without -SkipInstall to install them."
        }
        Write-Host "Installing dependencies: $($MissingModules -join ', ')"
        Invoke-Checked $VenvPython @("-m", "pip", "install", "--upgrade", "pip") "pip upgrade"
        Invoke-Checked $VenvPython @("-m", "pip", "install", "-r", $RequirementsPath) "Dependency installation"
    }

    if (-not (Test-VenvModule "PySide6") -or -not (Test-VenvModule "serial")) {
        throw "Dependency verification failed after installation. Run with -ResetVenv to rebuild the environment."
    }

    if ($CheckOnly) {
        Write-Host "Environment check passed." -ForegroundColor Green
        exit 0
    }

    Write-Host "Starting application..." -ForegroundColor Green
    Invoke-Checked $VenvPython @($AppPath) "Application"
    exit 0
}
catch {
    Write-Host ""
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Log file: $LogPath" -ForegroundColor Yellow
    Write-Host "Retry command: .\start_serial_console.ps1 -ResetVenv" -ForegroundColor Yellow
    exit 1
}
finally {
    if ($TranscriptStarted) {
        try { Stop-Transcript | Out-Null } catch { }
    }
}
