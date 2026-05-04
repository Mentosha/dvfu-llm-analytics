#!/usr/bin/env bash
# Проверяет, что LLM_PROXY_URL открывает доступ к Gemini API.
# Запускать перед docker compose up на сервере.

set -euo pipefail

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

: "${GEMINI_API_KEY:?GEMINI_API_KEY не задан}"

if [ -n "${LLM_PROXY_URL:-}" ]; then
  echo "1) TCP-доступ до прокси…"
  host=$(echo "$LLM_PROXY_URL" | sed -E 's#^.*@##; s#:[0-9]+$##')
  port=$(echo "$LLM_PROXY_URL" | sed -E 's#^.*:([0-9]+)$#\1#')
  nc -zv -w 5 "$host" "$port" || { echo "FAIL: TCP до $host:$port"; exit 1; }
  proxy_arg=(-x "$LLM_PROXY_URL")
else
  echo "1) LLM_PROXY_URL пуст — идём в Gemini напрямую."
  proxy_arg=()
fi

echo
echo "2) Gemini API…"
http_code=$(curl -s -o /tmp/gemini-check.json -w "%{http_code}" \
    --max-time 30 \
    "${proxy_arg[@]}" \
    -H "x-goog-api-key: $GEMINI_API_KEY" \
    "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1")

echo "HTTP $http_code"
if [ "$http_code" != "200" ]; then
  cat /tmp/gemini-check.json
  exit 1
fi
echo "OK: Gemini API отвечает."
