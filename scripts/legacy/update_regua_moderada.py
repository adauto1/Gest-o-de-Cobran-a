from app.main import SessionLocal, CollectionRule

def update_moderada():
    db = SessionLocal()
    
    # NOVAS MENSAGENS FORNECIDAS PELO USUÁRIO PARA RÉGUA MODERADA
    updates = {
        0: """Olá {nome},

Financeiro Portal Móveis.

Passando para lembrar que sua parcela vence hoje.

Notamos que você tem algumas parcelas em atraso. Que tal regularizar essa também para não acumular?

*Como pagar:*
📱 Pix - Chave CNPJ
🏦 Boleto - É só pedir

Precisa negociar? Estamos aqui para ajudar:
(67) 99916-1881

Atenciosamente,
Financeiro Portal Móveis""",

        3: """Olá {nome},

Financeiro Portal Móveis.

Notamos mais uma parcela em atraso.

*Situação atual:*
- Parcelas pendentes: {quantidade_parcelas}

Vamos colocar isso em dia? Podemos ajudar!

*Formas de pagamento:*
📱 Pix
🏦 Boleto atualizado

Fale conosco para negociar:
(67) 99916-1881

Atenciosamente,
Financeiro Portal Móveis""",
        
        7: """{nome},

Financeiro Portal Móveis

*Parcelas em aberto:* {quantidade_parcelas}

Sua situação precisa de atenção.

Importante regularizar para manter seu crédito em dia e evitar complicações futuras.

*Como regularizar:*
📱 Pix: {chave_pix}
🏦 Boleto

Vamos conversar? Ligue para:
(67) 99916-1881

Atenciosamente,
Financeiro Portal Móveis""",
        
        15: """{nome},

Financeiro Portal Móveis

*Parcelas vencidas:* {quantidade_parcelas}
*Dias de atraso:* 15 dias

Sua situação requer atenção urgente.

Para evitar negativação e manter seu crédito ativo, é importante regularizar o quanto antes.

*Regularize agora:*
📱 Pix: {chave_pix}
🏦 Boleto

Podemos negociar as melhores condições:
(67) 99916-1881

Estamos à disposição para ajudar.

Atenciosamente,
Financeiro Portal Móveis""",
        
        25: """{nome},

Financeiro Portal Móveis

CPF: {cpf_mascarado}
Parcelas pendentes: {quantidade_parcelas}
Tempo de atraso: 25 dias

⚠️ Situação que requer atenção imediata

Para evitar a inclusão do seu nome nos órgãos de proteção ao crédito, solicitamos a regularização em até 48 horas.

Queremos ajudar você a resolver isso da melhor forma.

*Como regularizar:*
📱 Pix: {chave_pix}

📞 Fale conosco: (67) 99916-1881

Estamos à disposição para negociar.

Atenciosamente,
Financeiro Portal Móveis"""
    }

    count = 0
    for days, template in updates.items():
        # Busca a regra MODERADA para aquele gatilho (start_days)
        rule = db.query(CollectionRule).filter(
            CollectionRule.level == "MODERADA",
            CollectionRule.start_days == days
        ).first()
        
        if rule:
            rule.template_message = template
            count += 1
            print(f"Regra MODERADA D+{days} atualizada.")
        else:
            # Tenta criar se não existir? Melhor apenas avisar pois o sistema deve ter as regras base.
            print(f"AVISO: Regra MODERADA D+{days} não encontrada.")

    db.commit()
    db.close()
    print(f"Total de {count} regras MODERADA atualizadas com sucesso.")

if __name__ == "__main__":
    update_moderada()
