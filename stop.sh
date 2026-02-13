#!/bin/bash

# CIS Compliance Dashboard - Stop Script
# Gracefully stops backend and frontend services

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="$SCRIPT_DIR/.pids"
BACKEND_PORT=5001
FRONTEND_PORT=8000

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}🛑 Stopping CIS Compliance Dashboard...${NC}"
echo ""

STOPPED=0

# Stop backend
if [ -f "$PID_DIR/backend.pid" ]; then
    BACKEND_PID=$(cat "$PID_DIR/backend.pid" 2>/dev/null)
    if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
        kill "$BACKEND_PID" 2>/dev/null
        echo -e "${GREEN}✓${NC} Backend stopped (PID: $BACKEND_PID)"
        STOPPED=1
    fi
    rm -f "$PID_DIR/backend.pid"
fi

# Stop frontend
if [ -f "$PID_DIR/frontend.pid" ]; then
    FRONTEND_PID=$(cat "$PID_DIR/frontend.pid" 2>/dev/null)
    if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
        kill "$FRONTEND_PID" 2>/dev/null
        echo -e "${GREEN}✓${NC} Frontend stopped (PID: $FRONTEND_PID)"
        STOPPED=1
    fi
    rm -f "$PID_DIR/frontend.pid"
fi

# Stop sync daemon
if [ -f "$PID_DIR/sync.pid" ]; then
    SYNC_PID=$(cat "$PID_DIR/sync.pid" 2>/dev/null)
    if [ -n "$SYNC_PID" ] && kill -0 "$SYNC_PID" 2>/dev/null; then
        kill "$SYNC_PID" 2>/dev/null
        echo -e "${GREEN}✓${NC} Sync daemon stopped (PID: $SYNC_PID)"
        STOPPED=1
    fi
    rm -f "$PID_DIR/sync.pid"
fi

# Kill any orphaned processes on our ports
ORPHAN_BACKEND=$(lsof -ti:$BACKEND_PORT 2>/dev/null)
if [ -n "$ORPHAN_BACKEND" ]; then
    echo "$ORPHAN_BACKEND" | xargs kill -9 2>/dev/null || true
    echo -e "${GREEN}✓${NC} Killed orphaned process on port $BACKEND_PORT"
    STOPPED=1
fi

ORPHAN_FRONTEND=$(lsof -ti:$FRONTEND_PORT 2>/dev/null)
if [ -n "$ORPHAN_FRONTEND" ]; then
    echo "$ORPHAN_FRONTEND" | xargs kill -9 2>/dev/null || true
    echo -e "${GREEN}✓${NC} Killed orphaned process on port $FRONTEND_PORT"
    STOPPED=1
fi

if [ $STOPPED -eq 0 ]; then
    echo "No running dashboard processes found."
else
    echo ""
    echo -e "${GREEN}👋 Dashboard stopped successfully.${NC}"
fi

echo ""
