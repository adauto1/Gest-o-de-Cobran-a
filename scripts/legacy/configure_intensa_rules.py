from app.main import SessionLocal, CollectionRule

def configure_rules():
    db = SessionLocal()
    
    print("--- Configurando Régua de Cobrança (INTENSA) ---")
    
    # Templates definidos pelo usuário
    msg_preventiva = """Oi {nome}! Tudo bem? 😊
É o Noah aqui da Portal Móveis!
Só passando para lembrar: você tem uma parcela de *R$ {valor}* vencendo dia *{data_vencimento}*.
*Como pagar:*
📱 *Pix* - Chave CNPJ (te mando por aqui)
💳 *Cartão* - Pague pelo app/site
🏦 *Boleto* - Posso te enviar atualizado
Precisa de algo? Só chamar! 👍
Abraço,
Noah - Portal Móveis"""

    msg_vencimento = """Oi {nome}! ⏰
É o Noah da Portal Móveis!
Hoje é o vencimento da sua parcela de *R$ {valor}*!
Pague agora e *evite juros e multa*:
📱 *Pix* - Chave CNPJ (te mando)
💳 *Cartão* - Acesse nosso site
🏦 *Boleto* - Peça aqui
Ainda dá tempo de quitar sem acréscimos! 😉
Abraço,
Noah - Portal Móveis"""

    # Definição das Regras
    # dias_atraso: negativo = antes do vencimento, 0 = hoje, positivo = atrasado
    rules_config = [
        {
            "name": "Intensa - Preventiva 5 dias",
            "start_days": -5,
            "end_days": -5,
            "template": msg_preventiva,
            "frequency": 30 # Só manda uma vez por mês/ciclo
        },
        {
            "name": "Intensa - Preventiva 3 dias",
            "start_days": -3,
            "end_days": -3,
            "template": msg_preventiva,
            "frequency": 30
        },
        {
            "name": "Intensa - Dia do Vencimento",
            "start_days": 0,
            "end_days": 0,
            "template": msg_vencimento,
            "frequency": 30
        }
    ]
    
    for rc in rules_config:
        # Tenta achar regra existente pelos dias e nível INTENSA
        # Como 'level' não é único, e start_days também não, vamos tentar casar start/end
        rule = db.query(CollectionRule).filter(
            CollectionRule.start_days == rc["start_days"],
            CollectionRule.end_days == rc["end_days"],
            CollectionRule.level == "INTENSA"
        ).first()
        
        if rule:
            print(f"Atualizando regra existente: {rc['name']}")
            rule.template_message = rc['template']
            rule.frequency = rc['frequency']
            rule.priority = 10
            rule.active = True
            rule.default_action = "WHATSAPP"
        else:
            print(f"Criando nova regra: {rc['name']}")
            rule = CollectionRule(
                level="INTENSA",
                start_days=rc['start_days'],
                end_days=rc['end_days'],
                default_action="WHATSAPP",
                template_message=rc['template'],
                frequency=rc['frequency'],
                priority=10,
                active=True
            )
            db.add(rule)
            
    db.commit()
    print("✅ Regras configuradas com sucesso!")

if __name__ == "__main__":
    configure_rules()
