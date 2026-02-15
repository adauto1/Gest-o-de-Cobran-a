from app.main import SessionLocal, Configuracoes

def check_config():
    db = SessionLocal()
    config = db.query(Configuracoes).first()
    if config:
        print(f"WhatsApp Ativo: {config.whatsapp_ativo}")
        print(f"Modo Teste: {config.whatsapp_modo_teste}")
    else:
        print("Nenhuma configuração encontrada.")
    db.close()

if __name__ == "__main__":
    check_config()
