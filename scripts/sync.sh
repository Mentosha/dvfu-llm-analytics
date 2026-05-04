#!/usr/bin/env bash
# Заливает текущую папку на сервер через rsync (без GitHub).
#
# Запуск:
#   DEPLOY_SERVER=root@1.2.3.4 ./scripts/sync.sh

set -euo pipefail

SERVER="${DEPLOY_SERVER:?Установи DEPLOY_SERVER=user@host}"
TARGET_DIR="${DEPLOY_DIR:-/opt/dvfu-llm-analytics}"

cd "$(dirname "$0")/.."

echo "→ Создаю $TARGET_DIR на $SERVER"
ssh "$SERVER" "mkdir -p $TARGET_DIR"

echo "→ rsync (исключая .venv, .git, кэш, скрины)…"
rsync -az --delete \
  --exclude '.venv/' \
  --exclude 'venv/' \
  --exclude '.git/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.pytest_cache/' \
  --exclude '.mypy_cache/' \
  --exclude '.ruff_cache/' \
  --exclude '.DS_Store' \
  --exclude 'tmp/' \
  --exclude 'logs/' \
  --exclude 'data/runtime/' \
  --exclude 'data/uploads/' \
  ./ "$SERVER:$TARGET_DIR/"

echo "→ Заливаю .env (если на сервере его ещё нет)"
if ! ssh "$SERVER" "test -f $TARGET_DIR/.env"; then
  scp .env "$SERVER:$TARGET_DIR/.env"
  ssh "$SERVER" "chmod 600 $TARGET_DIR/.env"
fi

echo "→ Smoke-проверка прокси"
ssh "$SERVER" "cd $TARGET_DIR && bash scripts/check_proxy.sh" || {
  echo "⚠ check_proxy.sh упал — проверь LLM_PROXY_URL и квоту GEMINI"
}

echo "→ docker compose up -d --build"
ssh "$SERVER" "cd $TARGET_DIR && docker compose up -d --build"

echo "→ Статус и хвост логов:"
ssh "$SERVER" "cd $TARGET_DIR && docker compose ps && echo --- && docker compose logs --tail=30 bot"

echo
echo "✓ Готово."
