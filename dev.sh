#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "==> Stopping containers..."
docker compose -f "$ROOT/docker-compose.yml" down

echo "==> Building and starting containers..."
docker compose -f "$ROOT/docker-compose.yml" up -d --build

echo "==> Starting frontend dev server..."
cd "$ROOT/frontend"
npm run dev
