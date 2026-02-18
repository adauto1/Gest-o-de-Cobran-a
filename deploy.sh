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

# 3.5. Corrigir permissões do banco de dados
echo "🔐 Corrigindo permissões do banco de dados..."
mkdir -p "$APP_DIR/data"
chmod 755 "$APP_DIR/data"
if [ -f "$APP_DIR/data/app.db" ]; then
    chmod 664 "$APP_DIR/data/app.db"
fi

# 3.6. Migração automática do banco
echo "🗄️ Executando migrações automáticas..."
sqlite3 "$APP_DIR/data/app.db" "ALTER TABLE configuracoes ADD COLUMN whatsapp_instancia TEXT;" 2>/dev/null || true
sqlite3 "$APP_DIR/data/app.db" "ALTER TABLE configuracoes ADD COLUMN whatsapp_token TEXT;" 2>/dev/null || true
sqlite3 "$APP_DIR/data/app.db" "ALTER TABLE configuracoes ADD COLUMN updated_at TEXT;" 2>/dev/null || true
sqlite3 "$APP_DIR/data/app.db" "ALTER TABLE configuracoes ADD COLUMN whatsapp_modo_teste INTEGER DEFAULT 0;" 2>/dev/null || true

# 4. Reiniciar serviço
echo "🔄 Reiniciando serviço..."
sudo systemctl restart gestor-cobranca

echo "✅ Deploy concluído com sucesso!"
