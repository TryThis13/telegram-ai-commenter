#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

if command -v apt >/dev/null 2>&1; then
  sudo apt update
  sudo apt install -y python3 python3-venv python3-pip
fi

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r telegram_ai_commenter/requirements.txt

mkdir -p telegram_ai_commenter/data telegram_ai_commenter/sessions

if [ ! -f telegram_ai_commenter/.env ]; then
  cp deploy/env.example telegram_ai_commenter/.env
  echo "Created telegram_ai_commenter/.env from deploy/env.example. Fill real keys before running."
fi

if [ ! -f telegram_ai_commenter/config.json ]; then
  cp telegram_ai_commenter/config.example.json telegram_ai_commenter/config.json
  echo "Created telegram_ai_commenter/config.json from config.example.json. Edit it before running."
fi

echo "Install complete in $PROJECT_DIR"
