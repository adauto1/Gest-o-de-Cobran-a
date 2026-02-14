#!/bin/bash
# =====================================================
# Deploy Script — Gestão de Cobrança (Portal Móveis)
# /home/deploy/deploy.sh
# =====================================================
set -e

APP_DIR="/home/deploy/Gest-o-de-Cobran-a"
VENV="$APP_DIR/.venv"

echo "🚀 Iniciando deploy..."

# 1. Atualizar código
cd "$APP_DIR"
echo "📥 Atualizando código..."
git pull origin main

# 2. Ativar venv e instalar dependências
echo "📦 Instalando dependências..."
source "$VENV/bin/activate"
pip install -r requirements.txt --quiet

# 3. Migração do banco é automática!
# O startup da aplicação executa:
# - Base.metadata.create_all() → cria tabelas novas
# - _auto_migrate()            → adiciona colunas novas

# 4. Reiniciar serviço
echo "🔄 Reiniciando serviço..."
sudo systemctl restart gestao-cobranca

echo "✅ Deploy concluído com sucesso!"
