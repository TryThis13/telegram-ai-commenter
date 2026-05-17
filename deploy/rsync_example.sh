#!/usr/bin/env bash
set -euo pipefail

SERVER="${1:-root@YOUR_SERVER_IP}"
TARGET="${2:-/opt/agid-telegram-bot}"

rsync -avz \
  --exclude ".venv" \
  --exclude "__pycache__" \
  --exclude "telegram_ai_commenter/data" \
  --exclude "telegram_ai_commenter/.env" \
  ./ "$SERVER:$TARGET/"

echo "Synced project to $SERVER:$TARGET"
