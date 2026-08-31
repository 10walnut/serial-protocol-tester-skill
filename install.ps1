param(
    [ValidateSet("codex", "claude", "workbuddy", "harness", "custom")]
    [string]$Target = "codex",
    [string]$Destination = ""
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$SourceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillName = "serial-protocol-tester"

if (-not $Destination) {
    switch ($Target) {
        "codex" { $Destination = Join-Path $HOME ".codex\skills\$SkillName" }
        "claude" { $Destination = Join-Path $HOME ".claude\skills\$SkillName" }
        "workbuddy" {
            $SkillRoots = $env:WORKBUDDY_SKILL_DIRS
            if (-not $SkillRoots) {
                throw "Set WORKBUDDY_SKILL_DIRS or pass -Destination for your WorkBuddy installation."
            }
            $FirstRoot = ($SkillRoots -split [System.IO.Path]::PathSeparator)[0]
            $Destination = Join-Path $FirstRoot $SkillName
        }
        "harness" { $Destination = Join-Path (Get-Location) "skills\$SkillName" }
        "custom" { throw "-Target custom requires -Destination." }
    }
}

$ResolvedSource = [System.IO.Path]::GetFullPath($SourceRoot)
$ResolvedDestination = [System.IO.Path]::GetFullPath($Destination)
if ($ResolvedSource -eq $ResolvedDestination) {
    throw "Destination must be different from the source repository."
}

New-Item -ItemType Directory -Force -Path $ResolvedDestination | Out-Null
foreach ($File in @("SKILL.md", "LICENSE")) {
    Copy-Item -LiteralPath (Join-Path $ResolvedSource $File) -Destination $ResolvedDestination -Force
}
foreach ($RelativePath in @(
    "references\protocol-script-format.md",
    "scripts\protocol_core.py",
    "scripts\validate_protocol.py",
    "examples\sample_protocol.json"
)) {
    $TargetDirectory = Join-Path $ResolvedDestination (Split-Path -Parent $RelativePath)
    New-Item -ItemType Directory -Force -Path $TargetDirectory | Out-Null
    Copy-Item -LiteralPath (Join-Path $ResolvedSource $RelativePath) -Destination $TargetDirectory -Force
}

Write-Host "Installed $SkillName for $Target at $ResolvedDestination" -ForegroundColor Green
