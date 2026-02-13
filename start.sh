#!/bin/bash

# CIS Compliance Dashboard - Start Script
# Starts both backend (Flask) and frontend (HTTP server)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="$SCRIPT_DIR/.pids"

# Load .env file if it exists
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
fi
BACKEND_PORT=5001
FRONTEND_PORT=8000

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  🛡️  CIS Compliance Dashboard${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed. Please install Python 3.8 or higher.${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Python 3 found"

# Create PID directory
mkdir -p "$PID_DIR"

# Stop any existing processes
echo ""
echo "🧹 Cleaning up existing processes..."
if [ -f "$PID_DIR/backend.pid" ]; then
    OLD_PID=$(cat "$PID_DIR/backend.pid" 2>/dev/null)
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        kill "$OLD_PID" 2>/dev/null || true
        echo "   Stopped existing backend (PID: $OLD_PID)"
    fi
    rm -f "$PID_DIR/backend.pid"
fi

if [ -f "$PID_DIR/frontend.pid" ]; then
    OLD_PID=$(cat "$PID_DIR/frontend.pid" 2>/dev/null)
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        kill "$OLD_PID" 2>/dev/null || true
        echo "   Stopped existing frontend (PID: $OLD_PID)"
    fi
    rm -f "$PID_DIR/frontend.pid"
fi

if [ -f "$PID_DIR/sync.pid" ]; then
    OLD_PID=$(cat "$PID_DIR/sync.pid" 2>/dev/null)
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        kill "$OLD_PID" 2>/dev/null || true
        echo "   Stopped existing sync daemon (PID: $OLD_PID)"
    fi
    rm -f "$PID_DIR/sync.pid"
fi

# Kill any orphaned processes on our ports
lsof -ti:$BACKEND_PORT 2>/dev/null | xargs kill -9 2>/dev/null || true
lsof -ti:$FRONTEND_PORT 2>/dev/null | xargs kill -9 2>/dev/null || true
sleep 1

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
cd "$SCRIPT_DIR"
python3 -m pip install -q -r requirements.txt
echo -e "${GREEN}✓${NC} Dependencies installed"

# Start backend
echo ""
echo "🔧 Starting Flask backend on http://localhost:$BACKEND_PORT..."
cd "$SCRIPT_DIR/backend"
python3 app.py > "$SCRIPT_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > "$PID_DIR/backend.pid"

# Wait for backend to start
sleep 2

# Check if backend started successfully
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "${RED}❌ Backend failed to start. Check backend.log for details.${NC}"
    cat "$SCRIPT_DIR/backend.log"
    exit 1
fi
echo -e "${GREEN}✓${NC} Backend started (PID: $BACKEND_PID)"

# Start frontend server
echo ""
echo "🎨 Starting frontend server on http://localhost:$FRONTEND_PORT..."
cd "$SCRIPT_DIR/frontend"
python3 -m http.server $FRONTEND_PORT > /dev/null 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > "$PID_DIR/frontend.pid"
sleep 1

if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    echo -e "${RED}❌ Frontend failed to start.${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Frontend started (PID: $FRONTEND_PID)"

cd "$SCRIPT_DIR"

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  ✅ Dashboard is ready!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  📊 Dashboard:  http://localhost:$FRONTEND_PORT"
echo "  🔌 API:        http://localhost:$BACKEND_PORT"
echo ""
echo "  To stop:       ./stop.sh"
echo ""

# Start sync daemon
echo "🔄 Starting sync daemon..."
cd "$SCRIPT_DIR/backend"
python3 sync_daemon.py > "$SCRIPT_DIR/sync.log" 2>&1 &
SYNC_PID=$!
echo $SYNC_PID > "$PID_DIR/sync.pid"
sleep 1

if ! kill -0 $SYNC_PID 2>/dev/null; then
    echo -e "${RED}⚠ Sync daemon failed to start. Check sync.log for details.${NC}"
else
    echo -e "${GREEN}✓${NC} Sync daemon started (PID: $SYNC_PID)"
fi

cd "$SCRIPT_DIR"

# Handle cleanup on Ctrl+C
cleanup() {
    echo ""
    echo "👋 Stopping dashboard..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    kill $SYNC_PID 2>/dev/null || true
    rm -f "$PID_DIR/backend.pid" "$PID_DIR/frontend.pid" "$PID_DIR/sync.pid"
    echo "Dashboard stopped."
    exit 0
}

trap cleanup SIGINT SIGTERM

# Keep script running
wait
