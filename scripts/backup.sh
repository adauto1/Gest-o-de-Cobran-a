#!/usr/bin/env bash
set -euo pipefail
mkdir -p backups
TS=$(date +"%Y%m%d_%H%M%S")
SRC="data/app.db"
if [ ! -f "$SRC" ]; then
  echo "Banco não encontrado em $SRC"
  exit 1
fi
cp "$SRC" "backups/app_${TS}.db"
echo "OK: backups/app_${TS}.db"
