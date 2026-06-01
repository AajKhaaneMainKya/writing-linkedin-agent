#!/usr/bin/env bash
# Setup script for the content pipeline.
# Safe to run multiple times — every step checks before acting.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQ="$SCRIPT_DIR/requirements.txt"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
err()  { echo -e "${RED}✗${NC}  $*"; }
step() { echo -e "\n${BOLD}$*${NC}"; }

echo ""
echo -e "${BOLD}=== Content Pipeline Setup ===${NC}"

# ── 1. Python 3.10+ ───────────────────────────────────────────────────────────
step "1. Python"

PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null; then
        ver=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON="$candidate"
            ok "Python $ver ($PYTHON)"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    err "Python 3.10+ not found."
    echo "   Install: https://www.python.org/downloads/"
    exit 1
fi

# ── 2. pip packages ───────────────────────────────────────────────────────────
step "2. Python packages"

# Check if all required packages are already present
MISSING=0
while IFS= read -r pkg; do
    [[ -z "$pkg" || "$pkg" == \#* ]] && continue
    import_name="${pkg%%[>=<]*}"          # strip version specifier
    # Map package name to import name for the ones that differ
    case "$import_name" in
        beautifulsoup4) import_name="bs4" ;;
        python-dotenv)  import_name="dotenv" ;;
    esac
    if ! "$PYTHON" -c "import $import_name" 2>/dev/null; then
        MISSING=1
        break
    fi
done < "$REQ"

if [ "$MISSING" -eq 0 ]; then
    ok "All Python packages already installed"
else
    echo "   Installing from requirements.txt..."
    "$PYTHON" -m pip install -r "$REQ" --break-system-packages --quiet
    ok "Python packages installed"
fi

# ── 3. Playwright + Chromium ──────────────────────────────────────────────────
step "3. Playwright (deep scraping fallback)"

if ! "$PYTHON" -c "import playwright" 2>/dev/null; then
    echo "   Installing Playwright..."
    "$PYTHON" -m pip install playwright --break-system-packages --quiet
fi

# playwright install chromium is idempotent — skips if browser already present
echo "   Ensuring Chromium browser is installed..."
"$PYTHON" -m playwright install chromium --quiet 2>/dev/null \
    || "$PYTHON" -m playwright install chromium
ok "Playwright + Chromium ready"

# ── 4. .env file ──────────────────────────────────────────────────────────────
step "4. Environment config"

if [ -f "$SCRIPT_DIR/.env" ]; then
    ok ".env already exists"
else
    cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
    ok ".env created from .env.example"
fi

# ── 5. Ollama ─────────────────────────────────────────────────────────────────
step "5. Ollama"

if ! command -v ollama &>/dev/null; then
    warn "Ollama not installed."
    echo ""
    echo "   Install it, then come back:"
    echo "     macOS:  brew install ollama"
    echo "     Linux:  curl -fsSL https://ollama.com/install.sh | sh"
    echo ""
    echo "   Then pull the default model and start the server:"
    echo "     ollama pull mistral"
    echo "     ollama serve"
    echo ""
    echo "   Setup is otherwise complete — run this script again after installing Ollama."
    exit 0
fi

ok "Ollama installed ($(ollama --version 2>/dev/null | head -1))"

# Check if Ollama server is running
OLLAMA_URL="${OLLAMA_BASE_URL:-https://ollama-production-9144.up.railway.app}"
if curl -sf "$OLLAMA_URL" &>/dev/null; then
    ok "Ollama server running at $OLLAMA_URL"

    # Check for the default model
    DEFAULT_MODEL="${OLLAMA_MODEL:-mistral}"
    if ollama list 2>/dev/null | grep -q "^$DEFAULT_MODEL"; then
        ok "$DEFAULT_MODEL model available"
    else
        warn "$DEFAULT_MODEL not found locally — pulling now (this takes a few minutes)..."
        ollama pull "$DEFAULT_MODEL"
        ok "$DEFAULT_MODEL ready"
    fi
else
    warn "Ollama installed but server is not running."
    echo "   Start it in a separate terminal before running the pipeline:"
    echo "     ollama serve"
    echo ""
    echo "   If you haven't pulled a model yet:"
    echo "     ollama pull mistral"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}=== Setup complete ===${NC}"
echo ""
echo "Run the pipeline (make sure 'ollama serve' is running first):"
echo ""
echo "  python pipeline.py \"your topic here\""
echo ""
