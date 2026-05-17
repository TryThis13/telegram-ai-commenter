#!/usr/bin/env bash
set -euo pipefail

journalctl -u agid-telegram-panel -f
