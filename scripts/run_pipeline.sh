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
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST http://localhost:8000/news/pipeline \
    --max-time 3600)
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$HTTP_CODE" = "200" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✓ Pipeline iniciado" >> "$PROJECT_DIR/logs/pipeline_cron.log" 2>/dev/null || true
elif [ "$HTTP_CODE" = "409" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⊘ Pipeline rechazado (ejecución en curso)" >> "$PROJECT_DIR/logs/pipeline_cron.log" 2>/dev/null || true
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✗ Error HTTP $HTTP_CODE: $BODY" >> "$PROJECT_DIR/logs/pipeline_cron.log" 2>/dev/null || true
fi
