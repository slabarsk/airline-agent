#!/bin/bash
set -e

echo ">>> airline-agent startup.sh başladı"
echo ">>> GATEWAY_URL: $GATEWAY_URL"
echo ">>> PORT: $PORT"

# Frontend build yoksa yap
if [ ! -d "/home/site/wwwroot/frontend/build" ]; then
    echo ">>> Frontend build yapılıyor..."
    cd /home/site/wwwroot/frontend
    npm install --production
    npm run build
    cd /home/site/wwwroot
fi

# FRONTEND_BUILD env var'ı set et (agent bunu kullanacak)
export FRONTEND_BUILD=/home/site/wwwroot/frontend/build

# Agent'ı gunicorn ile başlat
cd /home/site/wwwroot/agent-backend
exec gunicorn --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120 --access-logfile - --error-logfile - agent:app
