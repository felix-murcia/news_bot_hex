#!/usr/bin/env bash
# Ejecuta el news pipeline cada hora vía cron / systemd timer.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Cargar .env si existe
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
fi

# Ejecutar pipeline
curl -sf -X POST http://localhost:8000/news/pipeline \
    --max-time 3600 \
    --retry 2 \
    --retry-delay 60

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Pipeline ejecutado (código $?)" >> "$PROJECT_DIR/logs/pipeline_cron.log" 2>/dev/null || true
