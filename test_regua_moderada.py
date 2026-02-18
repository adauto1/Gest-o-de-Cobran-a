from app.main import SessionLocal, CollectionRule, Configuracoes
from app.services.whatsapp import enviar_whatsapp
import time

TEST_PHONE = "67998539477"

def test_send_moderada():
    db = SessionLocal()
    rules = db.query(CollectionRule).filter(
        CollectionRule.level == "MODERADA",
        CollectionRule.active == True
    ).order_by(CollectionRule.start_days).all()
    
    config = db.query(Configuracoes).first()
    modo_teste = config.whatsapp_modo_teste if config else True
    
    print(f"Iniciando disparos de teste (MODERADA) para {TEST_PHONE}...")
    
    # Dados de exemplo para o teste
    replacements = {
        "{nome}": "Cliente de Teste",
        "{NOME}": "Cliente de Teste",
        "{valor}": "R$ 450,00",
        "{VALOR}": "R$ 450,00",
        "{valor_com_juros}": "R$ 462,15",
        "{total}": "R$ 1.350,00",
        "{TOTAL}": "R$ 1.350,00",
        "{total_divida}": "R$ 1.350,00",
        "{dias_atraso}": "25",
        "{DIAS}": "25",
        "{dias}": "25",
        "{vencimento}": "10/02/2026",
        "{data_vencimento}": "10/02/2026",
        "{data}": "10/02/2026",
        "{DATA}": "10/02/2026",
        "{qtd}": "3",
        "{QTD}": "3",
        "{quantidade_parcelas}": "3",
        "{cpf}": "***.456.789-**",
        "{cpf_mascarado}": "***.456.789-**",
        "{telefone}": "(67) 99916-1881",
        "{chave_pix}": "financeiro@portalmoveis.com.br",
        "{link_pagamento}": "https://portalmoveis.com.br/pagar/teste"
    }

    for r in rules:
        msg = r.template_message
        for k, v in replacements.items():
            msg = msg.replace(k, v)
        
        # Corrigir gatilho para exibição (D-0 ou D+X)
        prefix = "D" + ("+" if r.start_days > 0 else "") if r.start_days != 0 else "D-"
        print(f"Enviando gatilho {prefix}{r.start_days}...")
        
        res = enviar_whatsapp(TEST_PHONE, msg, modo_teste=modo_teste)
        print(f"Resultado: {res}")
        time.sleep(2)

    db.close()
    print("Testes MODERADA concluídos.")

if __name__ == "__main__":
    test_send_moderada()
