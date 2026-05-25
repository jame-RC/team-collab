# TeamCollab plugin installer for Windows.
# Creates a symlink at ~/.claude/plugins/team-collab → this repo.
#Requires -Version 5.1

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoDir = Split-Path -Parent $ScriptDir
$PluginDir = Join-Path $env:USERPROFILE ".claude\plugins\team-collab"

Write-Host "=== TeamCollab Plugin Installer ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Repo:   $RepoDir"
Write-Host "Target: $PluginDir"
Write-Host ""

# 1. Install Python package in editable mode
Write-Host "[1/3] Installing Python package (editable)..." -ForegroundColor Yellow
try {
    & pip install -e $RepoDir --quiet
} catch {
    Write-Host "       WARNING: pip install failed. Please install manually:" -ForegroundColor Red
    Write-Host "       pip install -e `"$RepoDir`""
}

# 2. Create plugin symlink
Write-Host "[2/3] Creating plugin symlink..." -ForegroundColor Yellow
$PluginParent = Split-Path -Parent $PluginDir
if (-not (Test-Path $PluginParent)) {
    New-Item -ItemType Directory -Path $PluginParent -Force | Out-Null
}

if (Test-Path $PluginDir) {
    $item = Get-Item $PluginDir -Force
    if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
        Write-Host "       Symlink already exists, updating..."
        Remove-Item $PluginDir -Force
    } else {
        Write-Host "       ERROR: $PluginDir is a real directory (not a symlink)." -ForegroundColor Red
        Write-Host "       Please remove it manually and re-run."
        exit 1
    }
}

New-Item -ItemType SymbolicLink -Path $PluginDir -Target $RepoDir | Out-Null
Write-Host "       -> $PluginDir -> $RepoDir"

# 3. Verify
Write-Host "[3/3] Verifying..." -ForegroundColor Yellow
$PluginJson = Join-Path $PluginDir ".claude-plugin\plugin.json"
if (Test-Path $PluginJson) {
    Write-Host ""
    Write-Host "SUCCESS: TeamCollab plugin installed." -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:"
    Write-Host "  1. Restart Claude Code"
    Write-Host "  2. Type /team-init to bootstrap a new project"
    Write-Host "  3. (Optional) Configure GitHub Actions:"
    Write-Host "     gh secret set ANTHROPIC_API_KEY"
} else {
    Write-Host ""
    Write-Host "ERROR: plugin.json not found at expected path." -ForegroundColor Red
    Write-Host "       Check that the symlink points to the correct repo."
    exit 1
}
