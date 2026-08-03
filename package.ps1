<#
.SYNOPSIS
    Build a distributable zip for people without GitHub access to this repo
    (or without git at all). Backup path to "Code -> Download ZIP" on GitHub.

    Uses `git archive`, so the zip can only ever contain git-tracked files --
    .venv/, expense_data/, config/owners.local.yaml, .env, and .mm/ (all
    gitignored) are structurally impossible to include by accident, even if
    they exist locally.

.USAGE
    .\package.ps1
    Requires all changes you want included to be committed first -- git
    archive packages the last commit on the current branch, not your
    working-directory edits.
#>

$ErrorActionPreference = "Stop"
$ProjectDir = $PSScriptRoot
Set-Location $ProjectDir

$dirty = git status --porcelain
if ($dirty) {
    Write-Host "Warning: you have uncommitted changes. git archive packages the last commit, so they won't be included:" -ForegroundColor Yellow
    Write-Host $dirty
    Write-Host ""
}

$branch = (git rev-parse --abbrev-ref HEAD).Trim()
$shortSha = (git rev-parse --short HEAD).Trim()

$outDir = Join-Path $ProjectDir "dist"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$zipName = "monarch-account-summary-$shortSha.zip"
$zipPath = Join-Path $outDir $zipName

git archive --format=zip -o $zipPath $branch

Write-Host "Package created: $zipPath" -ForegroundColor Green
Write-Host "Contains only git-tracked files as of commit $shortSha on $branch -- no secrets, no local data."
Write-Host "Send this zip to whoever needs it. They extract it anywhere and run install.ps1 from inside."
