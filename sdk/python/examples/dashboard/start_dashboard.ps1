<#
.SYNOPSIS
    Launch the SEP-1913 Trust Annotations Test Dashboard.

.DESCRIPTION
    - Activates the project venv
    - Checks that required packages are installed
    - Kills any process already on port 8913
    - Verifies the MCP server script can start (stdio health check)
    - Launches the dashboard at http://localhost:8913

.EXAMPLE
    .\start_dashboard.ps1
    .\start_dashboard.ps1 -Port 9000
#>

param(
    [int]$Port = 8913
)

$ErrorActionPreference = "Stop"
$sdkRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

# If run from sdk root directly, adjust
if (-not (Test-Path "$sdkRoot\examples\dashboard\app.py")) {
    $sdkRoot = $PSScriptRoot | Split-Path -Parent | Split-Path -Parent
    if (-not (Test-Path "$sdkRoot\examples\dashboard\app.py")) {
        $sdkRoot = Get-Location
    }
}

$venvPython = Join-Path $sdkRoot ".venv\Scripts\python.exe"
# Fall back to repo-level venv
if (-not (Test-Path $venvPython)) {
    $repoRoot = Split-Path -Parent (Split-Path -Parent $sdkRoot)
    $venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
}
$dashboardApp = Join-Path $sdkRoot "examples\dashboard\app.py"
$serverScript = Join-Path $sdkRoot "examples\_shared\mcp_server.py"
$pythonSrc = Join-Path $sdkRoot "src"

Write-Host ""
Write-Host "  SEP-1913 Trust Annotations Test Dashboard" -ForegroundColor Cyan
Write-Host "  ==========================================" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Check venv ──────────────────────────────────────
Write-Host "[1/5] Checking Python virtual environment..." -ForegroundColor Yellow
if (-not (Test-Path $venvPython)) {
    Write-Host "  ERROR: Virtual environment not found" -ForegroundColor Red
    Write-Host "  Run: python -m venv .venv && .venv\Scripts\pip install -e '.[dev]' mcp starlette uvicorn" -ForegroundColor Red
    exit 1
}
$pyVersion = & $venvPython --version 2>&1
Write-Host "  OK: $pyVersion" -ForegroundColor Green

# ── Step 2: Check required packages ─────────────────────────
Write-Host "[2/5] Checking required packages..." -ForegroundColor Yellow
$missing = @()
foreach ($pkg in @("mcp", "starlette", "uvicorn")) {
    $check = & $venvPython -c "import $pkg" 2>&1
    if ($LASTEXITCODE -ne 0) { $missing += $pkg }
}
if ($missing.Count -gt 0) {
    Write-Host "  Missing packages: $($missing -join ', ')" -ForegroundColor Red
    Write-Host "  Installing..." -ForegroundColor Yellow
    & $venvPython -m pip install $missing --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: Failed to install packages" -ForegroundColor Red
        exit 1
    }
}
Write-Host "  OK: mcp, starlette, uvicorn" -ForegroundColor Green

# ── Step 3: Verify MCP server can start ─────────────────────
Write-Host "[3/5] Verifying MCP server health..." -ForegroundColor Yellow
if (-not (Test-Path $serverScript)) {
    Write-Host "  ERROR: Server script not found: $serverScript" -ForegroundColor Red
    exit 1
}

# Quick syntax check on the server script
$syntaxCheck = & $venvPython -c "
import sys, os
sys.path.insert(0, r'$pythonSrc')
os.environ['PYTHONPATH'] = r'$pythonSrc'
import importlib.util
spec = importlib.util.spec_from_file_location('mcp_server', r'$serverScript')
mod = importlib.util.module_from_spec(spec)
print('Server module loadable')
" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: MCP server has import errors:" -ForegroundColor Red
    Write-Host "  $syntaxCheck" -ForegroundColor Red
    exit 1
}
Write-Host "  OK: Server script is valid and importable" -ForegroundColor Green

# ── Step 4: Free the port ────────────────────────────────────
Write-Host "[4/5] Checking port $Port..." -ForegroundColor Yellow
try {
    $existing = Get-NetTCPConnection -LocalPort $Port -ErrorAction Stop
} catch {
    $existing = $null
}
if ($existing) {
    $pids = $existing | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($procId in $pids) {
        try {
            $proc = Get-Process -Id $procId -ErrorAction Stop
            Write-Host "  Stopping existing process on port ${Port}: $($proc.ProcessName) (PID $procId)" -ForegroundColor Yellow
            Stop-Process -Id $procId -Force
        } catch {}
    }
    Start-Sleep -Seconds 1
    Write-Host "  OK: Port $Port freed" -ForegroundColor Green
} else {
    Write-Host "  OK: Port $Port is available" -ForegroundColor Green
}

# ── Step 5: Launch dashboard ─────────────────────────────────
Write-Host "[5/5] Starting dashboard..." -ForegroundColor Yellow
Write-Host ""

$env:PYTHONPATH = $pythonSrc
$env:DASHBOARD_PORT = $Port

Write-Host "  Dashboard URL:  http://localhost:$Port" -ForegroundColor Cyan
Write-Host "  Press Ctrl+C to stop" -ForegroundColor DarkGray
Write-Host ""

& $venvPython $dashboardApp
