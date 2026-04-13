#!/usr/bin/env bash
# Instala y activa el systemd timer para el news pipeline.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SYSTEMD_DIR="$HOME/.config/systemd/user"

echo "📰 Instalando News Bot Pipeline Timer..."

# Crear directorio systemd user si no existe
mkdir -p "$SYSTEMD_DIR"

# Copiar unit files
cp "$SCRIPT_DIR/news-bot-pipeline.service" "$SYSTEMD_DIR/"
cp "$SCRIPT_DIR/news-bot-pipeline.timer" "$SYSTEMD_DIR/"

# Recargar daemon, habilitar e iniciar timer
systemctl --user daemon-reload
systemctl --user enable news-bot-pipeline.timer
systemctl --user start news-bot-pipeline.timer

echo ""
echo "✅ Timer instalado correctamente."
echo ""
echo "📊 Estado del timer:"
systemctl --user status news-bot-pipeline.timer --no-pager
echo ""
echo "📅 Próxima ejecución programada:"
systemctl --user list-timers news-bot-pipeline.timer --no-pager
echo ""
echo "📝 Ver logs de ejecución:"
echo "   journalctl --user -u news-bot-pipeline.service -f"
echo ""
echo "🔧 Comandos útiles:"
echo "   Detener:  systemctl --user stop news-bot-pipeline.timer"
echo "   Iniciar:  systemctl --user start news-bot-pipeline.timer"
echo "   Ver logs: journalctl --user -u news-bot-pipeline.service --since today"
echo "   Ejecutar ahora: systemctl --user start news-bot-pipeline.service"
