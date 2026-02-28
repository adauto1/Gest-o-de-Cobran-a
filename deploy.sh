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

# 2. Criar venv se não existir, ativar e instalar dependências
echo "📦 Instalando dependências..."
if [ ! -d "$VENV" ]; then
    echo "   → Criando ambiente virtual em $VENV ..."
    python3 -m venv "$VENV"
fi
source "$VENV/bin/activate"
pip install -r requirements.txt --quiet --break-system-packages

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
sqlite3 "$APP_DIR/data/app.db" "ALTER TABLE configuracoes ADD COLUMN whatsapp_client_token TEXT;" 2>/dev/null || true
sqlite3 "$APP_DIR/data/app.db" "ALTER TABLE configuracoes ADD COLUMN scheduler_hora_disparo INTEGER DEFAULT 9;" 2>/dev/null || true
sqlite3 "$APP_DIR/data/app.db" "ALTER TABLE configuracoes ADD COLUMN director_alert_min_installments INTEGER DEFAULT 3;" 2>/dev/null || true
sqlite3 "$APP_DIR/data/app.db" "ALTER TABLE customers ADD COLUMN msgs_ativo INTEGER DEFAULT 1;" 2>/dev/null || true
sqlite3 "$APP_DIR/data/app.db" "CREATE TABLE IF NOT EXISTS reconciliation_stats (id INTEGER PRIMARY KEY, date DATE UNIQUE, total_paid_erp INTEGER, normally_paid INTEGER, cancelled_or_deleted INTEGER, details_json TEXT, created_at DATETIME, updated_at DATETIME);" 2>/dev/null || true
sqlite3 "$APP_DIR/data/app.db" "CREATE TABLE IF NOT EXISTS conferencia_titulos (id INTEGER PRIMARY KEY, data_processamento DATETIME, resumo_json TEXT, detalhes_json TEXT, created_at DATETIME);" 2>/dev/null || true
sqlite3 "$APP_DIR/data/app.db" "ALTER TABLE customers ADD COLUMN perfil_devedor TEXT DEFAULT 'NORMAL';" 2>/dev/null || true
sqlite3 "$APP_DIR/data/app.db" "ALTER TABLE configuracoes ADD COLUMN pix_chave TEXT;" 2>/dev/null || true
sqlite3 "$APP_DIR/data/app.db" "ALTER TABLE configuracoes ADD COLUMN pix_tipo TEXT DEFAULT 'CNPJ';" 2>/dev/null || true
sqlite3 "$APP_DIR/data/app.db" "ALTER TABLE configuracoes ADD COLUMN meta_contatos_diarios INTEGER DEFAULT 20;" 2>/dev/null || true
sqlite3 "$APP_DIR/data/app.db" "ALTER TABLE configuracoes ADD COLUMN meta_promessas_diarios INTEGER DEFAULT 5;" 2>/dev/null || true

# 4. Reiniciar serviço
echo "🔄 Reiniciando serviço..."
sudo systemctl restart gestor-cobranca

echo "✅ Deploy concluído com sucesso!"
