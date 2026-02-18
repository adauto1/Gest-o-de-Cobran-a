from app.main import SessionLocal, Configuracoes

def enable_real_mode():
    db = SessionLocal()
    
    # Busca config existente ou cria nova
    config = db.query(Configuracoes).first()
    if not config:
        print("Criando nova configuração...")
        config = Configuracoes(whatsapp_ativo=True, whatsapp_modo_teste=False)
        db.add(config)
    else:
        print("Atualizando configuração existente...")
        config.whatsapp_ativo = True
        config.whatsapp_modo_teste = False # DESATIVA MODO TESTE
    
    db.commit()
    print(f"Configuração Salva: Ativo={config.whatsapp_ativo}, Modo Teste={config.whatsapp_modo_teste}")
    db.close()

if __name__ == "__main__":
    enable_real_mode()
