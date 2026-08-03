<#
.SYNOPSIS
    One-click setup for monarch-account-summary. Installs Python if needed,
    creates the virtual environment, installs dependencies, and adds a
    Desktop shortcut that launches the app -- no manual Python/venv steps.

.USAGE
    Right-click this file -> "Run with PowerShell". Or from a PowerShell
    prompt in this folder: .\install.ps1
#>

$ErrorActionPreference = "Stop"
$ProjectDir = $PSScriptRoot
Set-Location $ProjectDir

Write-Host "== Monarch Account Summary setup ==" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# 1. Find or install Python 3.10+
# ---------------------------------------------------------------------------
function Get-UsablePython {
    $candidates = @()
    try {
        $pyLauncher = Get-Command py -ErrorAction Stop
        $candidates += $pyLauncher.Source
    } catch {}
    try {
        $pythonExe = Get-Command python -ErrorAction Stop
        $candidates += $pythonExe.Source
    } catch {}

    foreach ($exe in $candidates) {
        try {
            $verOutput = & $exe --version 2>&1
            if ($verOutput -match "Python (\d+)\.(\d+)") {
                $major = [int]$Matches[1]
                $minor = [int]$Matches[2]
                if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 10)) {
                    return $exe
                }
            }
        } catch {}
    }
    return $null
}

$python = Get-UsablePython

if (-not $python) {
    Write-Host "Python 3.10+ not found -- installing via winget..." -ForegroundColor Yellow
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        # winget has no "latest 3.x" meta-package id, so try recent releases
        # newest-first and fall back if the newest isn't in the catalog yet.
        $pythonWingetIds = @("Python.Python.3.14", "Python.Python.3.13", "Python.Python.3.12")
        $installed = $false
        foreach ($id in $pythonWingetIds) {
            & winget install --id $id -e --silent --accept-package-agreements --accept-source-agreements
            if ($?) {
                $installed = $true
                break
            }
        }
        if (-not $installed) {
            Write-Host "winget install failed. Please install Python 3.10+ manually from https://python.org/downloads and re-run this script." -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "winget is not available on this machine. Please install Python 3.10+ manually from https://python.org/downloads (check 'Add python.exe to PATH' during install) and re-run this script." -ForegroundColor Red
        exit 1
    }

    # winget updates PATH for new processes, but this running process still has
    # the old PATH -- refresh it from the registry before re-checking.
    $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machinePath;$userPath"

    $python = Get-UsablePython
    if (-not $python) {
        Write-Host "Python was installed but this window can't see it yet. Close this window, open a new PowerShell prompt, and re-run .\install.ps1." -ForegroundColor Red
        exit 1
    }
}

Write-Host "Using Python: $python" -ForegroundColor Green

# ---------------------------------------------------------------------------
# 2. Create the virtual environment (idempotent)
# ---------------------------------------------------------------------------
$venvDir = Join-Path $ProjectDir ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    & $python -m venv $venvDir
} else {
    Write-Host "Virtual environment already exists, reusing it." -ForegroundColor Cyan
}

# ---------------------------------------------------------------------------
# 3. Install dependencies
# ---------------------------------------------------------------------------
Write-Host "Installing dependencies (this can take a minute)..." -ForegroundColor Cyan
& $venvPython -m pip install --upgrade pip --quiet
& $venvPython -m pip install -e . --quiet
if (-not $?) {
    Write-Host "Dependency install failed -- see errors above." -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------------------
# 4. Seed a local owners config from the template if one doesn't exist yet
# ---------------------------------------------------------------------------
$ownersLocal = Join-Path $ProjectDir "config\owners.local.yaml"
$ownersExample = Join-Path $ProjectDir "config\owners.example.yaml"
if ((-not (Test-Path $ownersLocal)) -and (Test-Path $ownersExample)) {
    Copy-Item $ownersExample $ownersLocal
    Write-Host "Created config\owners.local.yaml from the template -- edit it with real Monarch Owner names before syncing." -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# 5. Create expense_data folders so they're visibly ready to use. "input" is
#    where the budget workbook (and a CSV export, if not using live fetch)
#    has to be placed manually -- this is real financial data, so it's
#    gitignored and never ships in the repo/zip; nothing can pre-populate it.
# ---------------------------------------------------------------------------
$inputDir = Join-Path $ProjectDir "expense_data\input"
$outputDir = Join-Path $ProjectDir "expense_data\output"
New-Item -ItemType Directory -Force -Path $inputDir | Out-Null
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

$readmePath = Join-Path $inputDir "PUT_YOUR_FILES_HERE.txt"
if (-not (Test-Path $readmePath)) {
    @"
Put your budget workbook (.xlsx) here -- e.g. "2026 Spending.xlsx".

If syncing from a CSV export instead of "Fetch live from Monarch" in the
app, put the Monarch transactions CSV export here too.

This folder holds real financial data. It's excluded from git and never
included in a downloaded zip -- these files have to be placed here by hand
on each machine that runs the app.
"@ | Out-File -FilePath $readmePath -Encoding utf8
}

# ---------------------------------------------------------------------------
# 6. Desktop shortcut that launches the app with one double-click
# ---------------------------------------------------------------------------
$desktop = [System.Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "Monarch Account Summary.lnk"
$streamlitExe = Join-Path $venvDir "Scripts\streamlit.exe"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $streamlitExe
$shortcut.Arguments = "run app.py"
$shortcut.WorkingDirectory = $ProjectDir
$shortcut.Description = "Launch the Monarch Account Summary app"
$shortcut.Save()

Write-Host ""
Write-Host "== Setup complete ==" -ForegroundColor Green
Write-Host "A 'Monarch Account Summary' shortcut was added to your Desktop."
Write-Host "Double-click it to launch the app -- it opens in your browser, no terminal needed."
Write-Host "First time in the app: open Settings and save Monarch credentials (and Gmail, if you want email alerts)."
Write-Host "Also: put your budget workbook .xlsx (and CSV export, if not using live fetch) into expense_data\input -- see the note left in that folder."
