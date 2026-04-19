#!/bin/bash
set -e

# Script'in bulunduğu klasörü bul (Azure bunu dinamik path'e çıkartıyor)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo ">>> airline-agent startup.sh başladı"
echo ">>> SCRIPT_DIR: $SCRIPT_DIR"
echo ">>> GATEWAY_URL: ${GATEWAY_URL:0:60}..."
echo ">>> PORT: $PORT"

# Ls ile ne var görelim
echo ">>> İçerik:"
ls -la | head -10

export FRONTEND_BUILD="$SCRIPT_DIR/frontend/build"
echo ">>> FRONTEND_BUILD: $FRONTEND_BUILD"

if [ -d "$FRONTEND_BUILD" ]; then
    echo ">>> Frontend build dizin var"
    ls "$FRONTEND_BUILD" | head -5
else
    echo "!!! FRONTEND_BUILD dizin yok!"
fi

export MCP_SERVER_PATH="$SCRIPT_DIR/mcp-server/server.py"
echo ">>> MCP_SERVER_PATH: $MCP_SERVER_PATH"

if [ ! -f "$MCP_SERVER_PATH" ]; then
    echo "!!! MCP server dosya yok!"
fi

# Agent'ı başlat
cd "$SCRIPT_DIR/agent-backend"
echo ">>> Gunicorn başlatılıyor..."
exec gunicorn --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120 --access-logfile - --error-logfile - agent:app
