#!/usr/bin/env bash
# DataRadar - Mac/Linux Setup Script (uv)
# Usage: chmod +x scripts/setup.sh && ./scripts/setup.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail()  { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

echo ""
echo "=================================================="
echo "   DataRadar Setup (Mac / Linux)"
echo "=================================================="
echo ""

# -- Navigate to project root --
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"
info "Project dir: $PROJECT_DIR"

# =================================================
#  1. Install uv (if not present)
# =================================================
if command -v uv &>/dev/null; then
    ok "uv: $(uv --version)"
else
    info "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    if command -v uv &>/dev/null; then
        ok "uv installed: $(uv --version)"
    else
        fail "uv installation failed. Install manually: https://docs.astral.sh/uv/getting-started/installation/"
    fi
fi

# =================================================
#  2. Install Python 3.12+ via uv (if needed)
# =================================================
info "Ensuring Python >= 3.12..."
uv python install 3.12 2>/dev/null || true
ok "Python ready"

# =================================================
#  3. Sync dependencies (creates .venv automatically)
# =================================================
info "Syncing dependencies..."
uv sync --all-extras
ok "Dependencies installed"

# =================================================
#  4. Install uvloop (Linux/Mac only, optional perf boost)
# =================================================
uv pip install uvloop 2>/dev/null && ok "uvloop installed" || warn "uvloop skipped (optional)"

# =================================================
#  5. Install Playwright browser
# =================================================
info "Installing Playwright Chromium..."
uv run playwright install chromium 2>/dev/null && ok "Playwright Chromium installed" || warn "Playwright install failed. Web scraping may not work."

# =================================================
#  6. Docker infrastructure
# =================================================
DOCKER_AVAILABLE=false
if command -v docker &>/dev/null; then
    if docker info &>/dev/null 2>&1; then
        DOCKER_AVAILABLE=true
        ok "Docker available"
    else
        warn "Docker installed but not running. Start Docker Desktop first."
    fi
else
    warn "Docker not installed, skipping infrastructure"
    warn "Knowledge base requires Docker (PostgreSQL + Redis + RSSHub)"
    warn "CLI-only mode available (RSS collect -> SQLite)"
fi

if [ "$DOCKER_AVAILABLE" = true ]; then
    info "Starting Docker infrastructure..."

    if [ ! -f "docker/.env" ]; then
        cp docker/.env.example docker/.env
        info "Created docker/.env from template"
    else
        info "docker/.env exists, skipping"
    fi

    cd docker
    docker compose up postgres redis rsshub -d 2>/dev/null || docker-compose up postgres redis rsshub -d 2>/dev/null
    cd "$PROJECT_DIR"

    info "Waiting for services..."
    sleep 5

    if docker compose -f docker/docker-compose.yml ps 2>/dev/null | grep -q "healthy\|running"; then
        ok "Docker services started"
    else
        warn "Services may not be ready yet. Check: docker compose -f docker/docker-compose.yml ps"
    fi
fi

# =================================================
#  7. Verify
# =================================================
echo ""
info "Verifying installation..."
uv run python -m dataradar status

# =================================================
#  8. Done
# =================================================
echo ""
echo "=================================================="
echo "   Setup complete!"
echo "=================================================="
echo ""
info "Usage:"
echo "  uv run dataradar status          # System status"
echo "  uv run dataradar fetch           # Run data collection"
echo "  uv run dataradar rss --days 1    # Query recent data"
echo ""

if [ "$DOCKER_AVAILABLE" = true ]; then
    info "Docker:"
    echo "  cd docker && docker compose up -d       # Start all"
    echo "  cd docker && docker compose down        # Stop all"
    echo "  cd docker && docker compose ps          # Check status"
    echo ""
fi

info "Config: edit config/config.yaml"
echo "  ai.api_key   - Your AI API key"
echo "  ai.model     - Model name (e.g. openai/gpt-4o)"
echo "  ai.api_base  - Custom endpoint (optional)"
echo ""
info "Docs: see README.md"
