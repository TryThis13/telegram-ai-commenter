#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

exec .venv/bin/python telegram_ai_commenter/main.py --config telegram_ai_commenter/config.json
