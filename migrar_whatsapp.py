from app.main import Base, engine, Configuracoes, WhatsappHistorico
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def migrate():
    log.info("Iniciando migração de tabelas WhatsApp...")
    
    # 1. Cria tabelas novas (WhatsappHistorico e Configuracoes, se não existirem)
    Base.metadata.create_all(bind=engine)
    log.info("Base.metadata.create_all executado.")

    # 2. Verifica se precisamos adicionar colunas em Configuracoes (caso a tabela já existisse vazia)
    # Mas como criamos o modelo agora, o create_all deve resolver se a tabela não existia.
    # Se a tabela 'configuracoes' JÁ EXISTIA (de outra versão), o create_all NÃO adiciona colunas.
    # Vamos tentar rodar o ALTER TABLE só por garantia, ignorando erro se já existir.
    
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE configuracoes ADD COLUMN whatsapp_ativo BOOLEAN DEFAULT FALSE"))
            log.info("Coluna whatsapp_ativo adicionada.")
        except Exception as e:
            log.info(f"Coluna whatsapp_ativo provavelmente já existe: {e}")

        try:
            conn.execute(text("ALTER TABLE configuracoes ADD COLUMN whatsapp_modo_teste BOOLEAN DEFAULT TRUE"))
            log.info("Coluna whatsapp_modo_teste adicionada.")
        except Exception as e:
            log.info(f"Coluna whatsapp_modo_teste provavelmente já existe: {e}")
        
        try:
            conn.execute(text("ALTER TABLE configuracoes ADD COLUMN updated_at DATETIME"))
            log.info("Coluna updated_at adicionada.")
        except Exception as e:
            log.info(f"Coluna updated_at provavelmente já existe: {e}")

if __name__ == "__main__":
    migrate()
    print("Migração concluída.")
