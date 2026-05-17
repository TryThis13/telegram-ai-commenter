#!/usr/bin/env bash
set -euo pipefail

journalctl -u agid-telegram-bot -f
