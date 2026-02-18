from app.main import SessionLocal, CollectionRule, Configuracoes
from app.services.whatsapp import enviar_whatsapp
import time

TEST_PHONE = "67998539477"

def test_send_intensa():
    db = SessionLocal()
    rules = db.query(CollectionRule).filter(
        CollectionRule.level == "INTENSA",
        CollectionRule.active == True
    ).order_by(CollectionRule.start_days).all()
    
    config = db.query(Configuracoes).first()
    modo_teste = config.whatsapp_modo_teste if config else True
    
    print(f"Iniciando disparos de teste (INTENSA) para {TEST_PHONE}...")
    
    # Dados de exemplo para o teste
    replacements = {
        "{nome}": "Cliente de Teste",
        "{NOME}": "Cliente de Teste",
        "{valor}": "R$ 800,00",
        "{VALOR}": "R$ 800,00",
        "{valor_com_juros}": "R$ 832,00",
        "{total}": "R$ 2.400,00",
        "{TOTAL}": "R$ 2.400,00",
        "{total_divida}": "R$ 2.400,00",
        "{dias_atraso}": "30",
        "{DIAS}": "30",
        "{dias}": "30",
        "{vencimento}": "15/02/2026",
        "{data_vencimento}": "15/02/2026",
        "{data}": "15/02/2026",
        "{DATA}": "15/02/2026",
        "{qtd}": "3",
        "{QTD}": "3",
        "{quantidade_parcelas}": "3",
        "{cpf}": "***.123.456-**",
        "{cpf_mascarado}": "***.123.456-**",
        "{telefone}": "(67) 99916-1881",
        "{chave_pix}": "pix@portalmoveis.com.br",
        "{link_pagamento}": "https://portalmoveis.com.br/pagar/teste-intenso"
    }

    # Usar um set para evitar disparar duplicatas no teste se houverem no banco
    sent_triggers = set()

    for r in rules:
        if r.start_days in sent_triggers:
             continue
             
        msg = r.template_message
        for k, v in replacements.items():
            msg = msg.replace(k, v)
        
        prefix = "D" + ("+" if r.start_days > 0 else "") if r.start_days != 0 else "D-"
        print(f"Enviando gatilho {prefix}{r.start_days}...")
        
        res = enviar_whatsapp(TEST_PHONE, msg, modo_teste=modo_teste)
        print(f"Resultado: {res}")
        sent_triggers.add(r.start_days)
        time.sleep(2)

    db.close()
    print("Testes INTENSA concluídos.")

if __name__ == "__main__":
    test_send_intensa()
