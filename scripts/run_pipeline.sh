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

# Ejecutar pipeline con timeout y manejo de errores mejorado
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST http://localhost:8000/news/pipeline \
    --header "X-API-Key: ${APP_API_KEY:-}" \
    --max-time 3600 \
    --connect-timeout 30 \
    --retry 3 \
    --retry-delay 5 \
    --retry-max-time 300 2>/dev/null) || {
    HTTP_CODE="000"
    BODY="Connection failed or timeout"
}

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

# Mejorar el logging con información adicional
if [ "$HTTP_CODE" = "200" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✓ Pipeline iniciado (HTTP $HTTP_CODE)" >> "$PROJECT_DIR/logs/pipeline_cron.log" 2>/dev/null || true
elif [ "$HTTP_CODE" = "409" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⊘ Pipeline rechazado (ejecución en curso) (HTTP $HTTP_CODE)" >> "$PROJECT_DIR/logs/pipeline_cron.log" 2>/dev/null || true
elif [ "$HTTP_CODE" = "500" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️ Error interno del servidor (HTTP $HTTP_CODE): $BODY" >> "$PROJECT_DIR/logs/pipeline_cron.log" 2>/dev/null || true
elif [ "$HTTP_CODE" = "503" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️ Servicio no disponible (HTTP $HTTP_CODE): $BODY" >> "$PROJECT_DIR/logs/pipeline_cron.log" 2>/dev/null || true
elif [ "$HTTP_CODE" = "000" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✗ Error de conexión (timeout o servidor no disponible)" >> "$PROJECT_DIR/logs/pipeline_cron.log" 2>/dev/null || true
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✗ Error HTTP $HTTP_CODE: $BODY" >> "$PROJECT_DIR/logs/pipeline_cron.log" 2>/dev/null || true
fi
