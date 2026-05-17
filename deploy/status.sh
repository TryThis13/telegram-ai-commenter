#!/usr/bin/env bash
set -euo pipefail

systemctl status agid-telegram-bot --no-pager || true
