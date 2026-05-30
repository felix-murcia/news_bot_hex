#!/bin/bash
set -e
cd "$(dirname "$0")"

COMPOSE="docker compose"

case "${1:-up}" in
  up)
    $COMPOSE up -d --build
    echo "Arrancando frontend dev server..."
    cd frontend && npm run dev
    ;;
  down)
    $COMPOSE down
    ;;
  restart)
    $COMPOSE down
    $COMPOSE up -d --build
    cd frontend && npm run dev
    ;;
  logs)
    $COMPOSE logs -f app
    ;;
  *)
    echo "Uso: $0 [up|down|restart|logs]"
    exit 1
    ;;
esac
