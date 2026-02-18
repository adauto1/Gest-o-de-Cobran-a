import logging
from sqlalchemy import text
from app.main import Base, engine

log = logging.getLogger(__name__)

def migrate_perfil():
    print("Iniciando migração de Perfil de Cobrança...")
    
    with engine.connect() as conn:
        conn.begin()
        try:
            # Adiciona coluna profile_cobranca se não existir
            # Melhor jeito em SQL bruto p/ SQLite/Postgres genérico (sem inspeção complexa)
            # É tentar adicionar e ignorar erro ou verificar antes.
            # Como é SQLite (provavelmente) ou Postgres, ALTER TABLE ADD COLUMN IF NOT EXISTS é seguro em PG,
            # mas em SQLite as vezes é chato. Vamos tentar catch.
            
            try:
                conn.execute(text("ALTER TABLE customers ADD COLUMN profile_cobranca VARCHAR(20) DEFAULT 'AUTOMATICO'"))
                print("✅ Coluna 'profile_cobranca' adicionada com sucesso.")
            except Exception as e:
                if "duplicate column" in str(e) or "already exists" in str(e):
                    print("⚠️ Coluna 'profile_cobranca' já existe.")
                else:
                    print(f"❌ Erro ao adicionar coluna: {e}")
                    # Em SQLite as vezes falha se não for nullable, mas pus default.
                    # Se falhar critico, vou ver o log.
            
        except Exception as e:
            print(f"Erro geral: {e}")

if __name__ == "__main__":
    migrate_perfil()
