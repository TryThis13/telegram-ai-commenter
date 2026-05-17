#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="/opt/agid-telegram-bot"

if [ "$PROJECT_DIR" != "$TARGET_DIR" ]; then
  echo "Warning: project is in $PROJECT_DIR, but service template expects $TARGET_DIR."
  echo "Recommended: move project to $TARGET_DIR or edit deploy/agid-telegram-bot.service."
fi

sudo cp "$PROJECT_DIR/deploy/agid-telegram-bot.service" /etc/systemd/system/agid-telegram-bot.service
sudo systemctl daemon-reload
sudo systemctl enable agid-telegram-bot
sudo systemctl restart agid-telegram-bot
sudo systemctl status agid-telegram-bot --no-pager
