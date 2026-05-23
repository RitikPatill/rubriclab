#!/usr/bin/env bash
# record_demo.sh — Start both servers, seed the demo database, and print the
# comparison URL so you can take a screenshot before stopping.
#
# Usage:
#   bash scripts/record_demo.sh
#
# Prerequisites:
#   make install       (install Python + Node dependencies)
#   cp .env.example .env && edit .env to add ANTHROPIC_API_KEY

set -euo pipefail

# ---------------------------------------------------------------------------
# Resolve repo root (works whether called from root or from scripts/)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ---------------------------------------------------------------------------
# Load .env if present
# ---------------------------------------------------------------------------
if [ -f "$ROOT/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$ROOT/.env"
    set +a
fi

# ---------------------------------------------------------------------------
# Guard: API key must be set
# ---------------------------------------------------------------------------
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    echo "❌  ANTHROPIC_API_KEY is not set."
    echo "    Copy .env.example to .env and add your key, then re-run."
    exit 1
fi

# ---------------------------------------------------------------------------
# Launch API server
# ---------------------------------------------------------------------------
echo "▶  Starting API server on :8000 …"
(cd "$ROOT/apps/api" && uvicorn src.api.main:app --host 0.0.0.0 --port 8000) &
API_PID=$!

# ---------------------------------------------------------------------------
# Launch web dev server
# ---------------------------------------------------------------------------
echo "▶  Starting web server on :3000 …"
(cd "$ROOT/apps/web" && npm run dev) &
WEB_PID=$!

# ---------------------------------------------------------------------------
# Cleanup on exit / interrupt
# ---------------------------------------------------------------------------
cleanup() {
    echo ""
    echo "⏹  Stopping servers (API PID=$API_PID, WEB PID=$WEB_PID) …"
    kill "$API_PID" "$WEB_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# ---------------------------------------------------------------------------
# Wait for API health check
# ---------------------------------------------------------------------------
echo "⏳  Waiting for API to be ready …"
MAX_TRIES=30
for i in $(seq 1 $MAX_TRIES); do
    if curl -sf "http://localhost:8000/health" >/dev/null 2>&1; then
        echo "✅  API is up."
        break
    fi
    if [ "$i" -eq "$MAX_TRIES" ]; then
        echo "❌  API did not become ready after $((MAX_TRIES * 2)) seconds."
        exit 1
    fi
    sleep 2
done

# ---------------------------------------------------------------------------
# Seed the demo database
# ---------------------------------------------------------------------------
echo ""
echo "🌱  Seeding demo database …"
cd "$ROOT"
python scripts/seed_demo.py

# ---------------------------------------------------------------------------
# Instructions
# ---------------------------------------------------------------------------
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Both servers are running."
echo ""
echo "  1. Open http://localhost:3000 — you should see 2 completed runs."
echo "  2. Take a screenshot and save it as docs/screenshot.png"
echo "  3. Click 'Compare' (or use the URL printed above) to see the diff."
echo "  4. Record a GIF if you like (LICEcap / peek), save as docs/demo.gif"
echo ""
echo "  Press Ctrl+C to stop the servers when you're done."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Block until the user presses Ctrl+C
wait
