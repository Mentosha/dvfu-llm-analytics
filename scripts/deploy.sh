#!/usr/bin/env bash
# Деплой dvfu-analytics-bot на сервер.
# Идемпотентен: на свежем сервере делает clone, дальше — pull + up -d --build.
#
# Что не трогает: существующие сервисы, контейнеры с другими именами.

set -euo pipefail

SERVER="${DEPLOY_SERVER:?Установи DEPLOY_SERVER=user@host}"
REPO_URL="${DEPLOY_REPO:?Установи DEPLOY_REPO=https://github.com/USER/REPO.git}"
TARGET_DIR="${DEPLOY_DIR:-/opt/dvfu-llm-analytics}"
LOCAL_ENV="${LOCAL_ENV:-.env}"

echo "→ Деплою на $SERVER в $TARGET_DIR из $REPO_URL"

# 1. clone или pull
ssh "$SERVER" bash -s <<EOF
set -euo pipefail
if [ ! -d "$TARGET_DIR/.git" ]; then
  git clone "$REPO_URL" "$TARGET_DIR"
else
  cd "$TARGET_DIR" && git pull --ff-only
fi
EOF

# 2. .env: если на сервере нет — заливаем локальный
if ! ssh "$SERVER" "test -f $TARGET_DIR/.env"; then
  if [ ! -f "$LOCAL_ENV" ]; then
    echo "Локальный $LOCAL_ENV не найден — нечего заливать"
    exit 3
  fi
  echo "→ Заливаю $LOCAL_ENV → $SERVER:$TARGET_DIR/.env"
  scp "$LOCAL_ENV" "$SERVER:$TARGET_DIR/.env"
fi

# 3. smoke-проверка прокси
ssh "$SERVER" "cd $TARGET_DIR && bash scripts/check_proxy.sh"

# 4. compose up
ssh "$SERVER" "cd $TARGET_DIR && docker compose up -d --build"

# 5. статус
ssh "$SERVER" "cd $TARGET_DIR && docker compose ps && docker compose logs --tail=30 bot"

echo "✓ Готово."
