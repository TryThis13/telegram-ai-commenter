#!/usr/bin/env bash
set -euo pipefail

systemctl stop agid-telegram-bot 2>/dev/null || true
pkill -f "telegram_ai_commenter/main.py" 2>/dev/null || true
echo "Bot stop command sent."
