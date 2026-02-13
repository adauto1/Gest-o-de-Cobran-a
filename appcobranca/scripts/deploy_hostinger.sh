#!/usr/bin/env bash
# Deploy rápido (Hostinger VPS / Ubuntu)
set -euo pipefail

echo "1) Checando Docker..."
docker --version >/dev/null 2>&1 || { echo "Instale Docker antes."; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "Instale docker compose plugin antes."; exit 1; }

echo "2) Preparando .env..."
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Arquivo .env criado. Edite SESSION_SECRET e senha do admin."
fi

echo "3) Subindo containers..."
docker compose up -d --build

echo "OK!"
echo "Acesse: http://SEU_IP:8000"
