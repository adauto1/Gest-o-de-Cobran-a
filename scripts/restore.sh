#!/usr/bin/env bash
set -euo pipefail
if [ $# -lt 1 ]; then
  echo "Uso: ./scripts/restore.sh backups/ARQUIVO.db"
  exit 1
fi
SRC="$1"
if [ ! -f "$SRC" ]; then
  echo "Arquivo não encontrado: $SRC"
  exit 1
fi
mkdir -p data
cp "$SRC" "data/app.db"
echo "OK: restaurado para data/app.db"
