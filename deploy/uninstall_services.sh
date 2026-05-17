#!/usr/bin/env bash
set -euo pipefail

sudo systemctl stop agid-telegram-bot 2>/dev/null || true
sudo systemctl stop agid-telegram-panel 2>/dev/null || true
sudo systemctl disable agid-telegram-bot 2>/dev/null || true
sudo systemctl disable agid-telegram-panel 2>/dev/null || true
sudo rm -f /etc/systemd/system/agid-telegram-bot.service
sudo rm -f /etc/systemd/system/agid-telegram-panel.service
sudo systemctl daemon-reload
echo "Services removed."
