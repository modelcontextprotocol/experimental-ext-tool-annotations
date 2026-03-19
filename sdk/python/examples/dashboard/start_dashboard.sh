#!/usr/bin/env bash
#
# Launch the SEP-1913 Trust Annotations Test Dashboard.
#
#   - Checks for a Python venv
#   - Verifies required packages are installed
#   - Kills any process already on the dashboard port
#   - Verifies the MCP server script can load
#   - Launches the dashboard at http://localhost:8913
#
# Usage:
#   cd sdk/python/examples/dashboard
#   chmod +x start_dashboard.sh
#   ./start_dashboard.sh
#   ./start_dashboard.sh 9000

set -euo pipefail

PORT="${1:-8913}"

# ── Resolve paths ────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SDK_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

DASHBOARD_APP="$SDK_ROOT/examples/dashboard/app.py"
SERVER_SCRIPT="$SDK_ROOT/examples/_shared/mcp_server.py"
PYTHON_SRC="$SDK_ROOT/src"

# Locate venv python: sdk-level first, then repo-level
VENV_PYTHON="$SDK_ROOT/.venv/bin/python"
if [ ! -f "$VENV_PYTHON" ]; then
    REPO_ROOT="$(cd "$SDK_ROOT/../.." && pwd)"
    VENV_PYTHON="$REPO_ROOT/.venv/bin/python"
fi

# ANSI colors
CYAN='\033[96m'
YELLOW='\033[93m'
GREEN='\033[92m'
RED='\033[91m'
DIM='\033[2m'
RST='\033[0m'

echo ""
echo -e "  ${CYAN}SEP-1913 Trust Annotations Test Dashboard${RST}"
echo -e "  ${CYAN}==========================================${RST}"
echo ""

# ── Step 1: Check venv ──────────────────────────────────────
echo -e "${YELLOW}[1/5] Checking Python virtual environment...${RST}"
if [ ! -f "$VENV_PYTHON" ]; then
    echo -e "  ${RED}ERROR: Virtual environment not found${RST}"
    echo -e "  ${RED}Run: python3 -m venv .venv && .venv/bin/pip install -e '.[dev]' mcp starlette uvicorn${RST}"
    exit 1
fi
PY_VERSION=$("$VENV_PYTHON" --version 2>&1)
echo -e "  ${GREEN}OK: $PY_VERSION${RST}"

# ── Step 2: Check required packages ─────────────────────────
echo -e "${YELLOW}[2/5] Checking required packages...${RST}"
MISSING=()
for pkg in mcp starlette uvicorn; do
    if ! "$VENV_PYTHON" -c "import $pkg" 2>/dev/null; then
        MISSING+=("$pkg")
    fi
done
if [ ${#MISSING[@]} -gt 0 ]; then
    echo -e "  ${RED}Missing packages: ${MISSING[*]}${RST}"
    echo -e "  ${YELLOW}Installing...${RST}"
    "$VENV_PYTHON" -m pip install "${MISSING[@]}" --quiet
fi
echo -e "  ${GREEN}OK: mcp, starlette, uvicorn${RST}"

# ── Step 3: Verify MCP server can start ─────────────────────
echo -e "${YELLOW}[3/5] Verifying MCP server health...${RST}"
if [ ! -f "$SERVER_SCRIPT" ]; then
    echo -e "  ${RED}ERROR: Server script not found: $SERVER_SCRIPT${RST}"
    exit 1
fi

if ! "$VENV_PYTHON" -c "
import sys, os
sys.path.insert(0, '$PYTHON_SRC')
os.environ['PYTHONPATH'] = '$PYTHON_SRC'
import importlib.util
spec = importlib.util.spec_from_file_location('mcp_server', '$SERVER_SCRIPT')
mod = importlib.util.module_from_spec(spec)
print('Server module loadable')
" 2>&1; then
    echo -e "  ${RED}ERROR: MCP server has import errors${RST}"
    exit 1
fi
echo -e "  ${GREEN}OK: Server script is valid and importable${RST}"

# ── Step 4: Free the port ────────────────────────────────────
echo -e "${YELLOW}[4/5] Checking port $PORT...${RST}"
PIDS=$(lsof -ti :"$PORT" 2>/dev/null || true)
if [ -n "$PIDS" ]; then
    echo -e "  ${YELLOW}Stopping existing process(es) on port $PORT: $PIDS${RST}"
    echo "$PIDS" | xargs kill -9 2>/dev/null || true
    sleep 1
    echo -e "  ${GREEN}OK: Port $PORT freed${RST}"
else
    echo -e "  ${GREEN}OK: Port $PORT is available${RST}"
fi

# ── Step 5: Launch dashboard ─────────────────────────────────
echo -e "${YELLOW}[5/5] Starting dashboard...${RST}"
echo ""

export PYTHONPATH="$PYTHON_SRC"
export DASHBOARD_PORT="$PORT"

echo -e "  ${CYAN}Dashboard URL:  http://localhost:$PORT${RST}"
echo -e "  ${DIM}Press Ctrl+C to stop${RST}"
echo ""

exec "$VENV_PYTHON" "$DASHBOARD_APP"
