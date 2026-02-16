from app.main import SessionLocal, CollectionRule

def configure_rules():
    db = SessionLocal()
    print("Configurando Réguas LEVE e MODERADA...")

    # Remover regras antigas desses níveis para evitar duplicação/conflito
    db.query(CollectionRule).filter(CollectionRule.level.in_(["LEVE", "MODERADA"])).delete(synchronize_session=False)
    db.commit()
    
    # --- LEVE ---
    # D+3
    r_leve_3 = CollectionRule(
        level="LEVE", start_days=3, end_days=3, priority=1, frequency=1, default_action="WHATSAPP",
        template_message="""Oi {nome}! 

É o Noah da Portal Móveis.

Notei que sua parcela de *{valor}* (venceu dia {data_vencimento}) ainda não foi quitada.

*Valor atualizado:* {valor_com_juros}

Sabemos que imprevistos acontecem. Vamos resolver juntos? 😊

*Como regularizar:*
📱 *Pix* - Chave CNPJ (te mando)
💳 *Cartão* - Acesse nosso site
🏦 *Boleto atualizado* - Posso enviar

Qualquer dúvida, me chama! 👍

Abraço,
Noah - Portal Móveis"""
    )

    # D+7
    r_leve_7 = CollectionRule(
        level="LEVE", start_days=7, end_days=7, priority=1, frequency=1, default_action="WHATSAPP",
        template_message="""Oi {nome},

Noah - Portal Móveis aqui.

Sua parcela de *{valor}* está com 7 dias de atraso desde {data_vencimento}.

*Valor atualizado:* {valor_com_juros}

Vamos regularizar? É rapidinho:
📱 Pix / 💳 Cartão / 🏦 Boleto

Evite que o atraso aumente! 😉

Me chama se precisar negociar.

Noah - Portal Móveis
{telefone}"""
    )
    
    # D+15
    r_leve_15 = CollectionRule(
        level="LEVE", start_days=15, end_days=15, priority=1, frequency=1, default_action="WHATSAPP",
        template_message="""{nome},

É o Noah da Portal Móveis.

Sua parcela está com *15 dias de atraso*.

*Valor atualizado:* {valor_com_juros}

⚠️ Importante regularizar para evitar:
❌ Negativação do nome
❌ Perda de crédito
❌ Aumento de juros

*Regularize agora:*
📱 Pix / 💳 Cartão / 🏦 Boleto

Ou negocie comigo: {telefone}

Noah - Portal Móveis"""
    )

    # D+25
    r_leve_25 = CollectionRule(
        level="LEVE", start_days=25, end_days=25, priority=1, frequency=1, default_action="WHATSAPP",
        template_message="""{nome},

Noah - Portal Móveis aqui.

Sua parcela está com *25 dias de atraso* e o valor atualizado é *{valor_com_juros}*.

⚠️ Importante regularizar para:
✅ Evitar negativação
✅ Manter seu crédito ativo
✅ Continuar aprovado para novas compras

*Como pagar:*
📱 Pix: Chave CNPJ (te mando)
💳 Cartão: Acesse nosso site
🏦 Boleto atualizado: Envio aqui

Quer facilitar o pagamento? Me chama que a gente negocia! 😊

Noah - Portal Móveis
{telefone}"""
    )


    # --- MODERADA ---
    # D-0
    r_mod_0 = CollectionRule(
        level="MODERADA", start_days=0, end_days=0, priority=2, frequency=1, default_action="WHATSAPP",
        template_message="""Oi {nome},

Noah - Portal Móveis.

Hoje vence sua parcela de *{valor}*.

Você já tem parcelas em atraso. Regularize essa para não aumentar o débito!

*Pague agora:*
📱 *Pix* - Chave CNPJ
💳 *Cartão* - Link de pagamento
🏦 *Boleto* - Envio aqui

Quer negociar todas as parcelas? Me chama!

Noah - Portal Móveis
{telefone}"""
    )

    # D+3
    r_mod_3 = CollectionRule(
        level="MODERADA", start_days=3, end_days=3, priority=2, frequency=1, default_action="WHATSAPP",
        template_message="""{nome},

Noah - Portal Móveis.

Mais uma parcela em atraso ({valor}).

*Total em aberto:* {total_divida}
*Parcelas atrasadas:* {quantidade_parcelas}

⚠️ Situação se agravando. Vamos resolver?

*Regularize:*
📱 Pix / 💳 Cartão / 🏦 Boleto

Ou negocie: {telefone}

Noah - Portal Móveis"""
    )
    
    # D+7
    r_mod_7 = CollectionRule(
        level="MODERADA", start_days=7, end_days=7, priority=2, frequency=1, default_action="WHATSAPP",
        template_message="""{nome},

COBRANÇA - Portal Móveis

*Parcelas em atraso:* {quantidade_parcelas}
*Valor total:* {total_divida}

Sua situação está ficando crítica.

🚨 Regularize para evitar:
❌ Negativação iminente
❌ Cobrança judicial
❌ Bloqueio de novas compras

*Formas de pagamento:*
📱 Pix: {chave_pix}
💳 Cartão: {link_pagamento}

NEGOCIE AGORA: {telefone}

Depto. Cobrança - Portal Móveis"""
    )

    # D+15
    r_mod_15 = CollectionRule(
        level="MODERADA", start_days=15, end_days=15, priority=2, frequency=1, default_action="WHATSAPP",
        template_message="""{nome},

URGENTE - Portal Móveis

*Total em atraso:* {total_divida}
*Parcelas vencidas:* {quantidade_parcelas}

⚠️ Situação GRAVE - 15 dias de atraso

Sem regularização IMEDIATA:
❌ Seu nome será NEGATIVADO
❌ Perda total de crédito
❌ Cobrança judicial

*REGULARIZE AGORA:*
📱 Pix: {chave_pix}
📞 Negociação: {telefone}

Última chance de acordo amigável.

Depto. Cobrança - Portal Móveis"""
    )

    # D+25
    r_mod_25 = CollectionRule(
        level="MODERADA", start_days=25, end_days=25, priority=2, frequency=1, default_action="WHATSAPP",
        template_message="""{nome},

NOTIFICAÇÃO FINAL - Portal Móveis

CPF: {cpf}
Débito total: *{total_divida}*
Parcelas vencidas: *{quantidade_parcelas}*

🔴 25 DIAS DE ATRASO

Esta é a ÚLTIMA COMUNICAÇÃO antes de:
❌ NEGATIVAÇÃO DEFINITIVA
❌ PROTESTO DO TÍTULO
❌ AÇÃO JUDICIAL

*48 HORAS PARA REGULARIZAR:*
📱 Pix: {chave_pix}
📞 Urgente: {telefone}

Departamento Jurídico
Portal Móveis"""
    )
    
    # --- INTENSA (Adicionando para cobrir gaps do teste) ---
    # D+3 (Para cobrir o caso "Start=3" que não existia) - C008 pode cair aqui se atraso for pequeno
    # Mas C008 no dataset tem D+30. C009 tem D+7.
    
    # D+7
    r_int_7 = CollectionRule(
        level="INTENSA", start_days=7, end_days=7, priority=3, frequency=1, default_action="WHATSAPP",
        template_message="""{nome},
URGENTE - Falta de Pagamento (INTENSA)
CPF: {cpf}
Débito: {total_divida}

Sua situação é delicada.
Regularize HOJE para evitar bloqueios.
Pix: {chave_pix}"""
    )

    # D+15
    r_int_15 = CollectionRule(
        level="INTENSA", start_days=15, end_days=15, priority=3, frequency=1, default_action="WHATSAPP",
        template_message="""{nome},
COBRANÇA JUDICIAL - PRÉ NOTIFICAÇÃO
Atraso de 15 dias identificado.
Perfil de risco: ALTO.

Evite protesto em cartório.
Pague agora: {link_pagamento}"""
    )
    
    # D+25
    r_int_25 = CollectionRule(
        level="INTENSA", start_days=25, end_days=25, priority=3, frequency=1, default_action="WHATSAPP",
        template_message="""{nome},
NOTIFICAÇÃO EXTRAJUDICIAL
25 Dias de Atraso.
Seu contrato será encaminhado para execução.

Última chance:
Pix: {chave_pix}"""
    )
    
    # D+30 (Existente, mas vamos garantir)
    r_int_30 = CollectionRule(
        level="INTENSA", start_days=30, end_days=30, priority=3, frequency=1, default_action="WHATSAPP",
        template_message="""{nome},
BLOQUEIO DE CRÉDITO
30 Dias de Atraso.
Seu nome será incluído nos órgãos de proteção ao crédito (SPC/Serasa).

Regularize imediatamente:
Pix: {chave_pix}"""
    )

    # Adicionar todas
    db.add_all([
        r_leve_3, r_leve_7, r_leve_15, r_leve_25,
        r_mod_0, r_mod_3, r_mod_7, r_mod_15, r_mod_25,
        r_int_7, r_int_15, r_int_25, r_int_30
    ])
    
    db.commit()
    print("✅ Regras LEVE e MODERADA configuradas com sucesso!")

if __name__ == "__main__":
    configure_rules()
