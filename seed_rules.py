"""
seed_rules.py — Popula as réguas de cobrança no banco de dados.
Idempotente: só insere se a tabela estiver vazia.
Rodar no VPS após o primeiro deploy: python seed_rules.py
"""
import sys
sys.path.insert(0, '.')
from app.core.database import SessionLocal
from app.models import CollectionRule

RULES = [
    # ── LEVE ──────────────────────────────────────────────────────────────────
    dict(level="LEVE", start_days=3, end_days=6, priority=3, frequency=3,
         default_action="WHATSAPP", active=True, template_message="""Olá, {NOME}! 😊
Aqui é do Financeiro Portal Móveis💙

📌 Passando pra avisar do vencimento
{PARCELAS}

Total em aberto: {TOTAL}

Se você já pagou, pode desconsiderar. ✅
Se preferir, posso te enviar PIX ou 2ª via por aqui. 💳✨

🤝 Qualquer coisa, é só me chamar.
📲 Retorno: (67) 99916-1881 | (67) 99656-9698"""),

    dict(level="LEVE", start_days=7, end_days=14, priority=4, frequency=7,
         default_action="WHATSAPP", active=True, template_message="""Oi, {NOME}! Tudo bem? 🙂
Aqui é do Financeiro Portal Móveis💙

📌 Lembrete do vencimento
{PARCELAS}

Total em aberto: {TOTAL}

Se já resolveu, desconsidere. ✅
Se quiser, me peça que eu envio PIX/2ª via agora. 💳

💙 Se precisar, estou por aqui pra ajudar.
📲 Retorno: (67) 99916-1881 | (67) 99656-9698"""),

    dict(level="LEVE", start_days=15, end_days=29, priority=5, frequency=5,
         default_action="WHATSAPP", active=True, template_message="""Boa tarde, {NOME}! 👋
Aqui é do Financeiro Portal Móveis💙

🗓️ Aviso do vencimento
{PARCELAS}

Total em aberto: {TOTAL}

Se já pagou, desconsidere. ✅
Se precisar, eu te envio PIX ou 2ª via por aqui para regularizar. 💳✅

✅ Caso tenha alguma dúvida, me avise.
📲 Retorno: (67) 99916-1881 | (67) 99656-9698"""),

    # ── MODERADA ──────────────────────────────────────────────────────────────
    dict(level="MODERADA", start_days=0, end_days=2, priority=1, frequency=0,
         default_action="WHATSAPP", active=True, template_message="""Olá, {NOME}! 😊
Aqui é do Financeiro Portal Móveis💙

🗓️ Só um lembrete: hoje vence sua parcela!
{PARCELAS}

Se você já pagou, pode desconsiderar. ✅
Se quiser, posso te enviar o PIX ou 2ª via agora. 💳

📲 Retorno: (67) 99916-1881 | (67) 99656-9698"""),

    dict(level="MODERADA", start_days=3, end_days=6, priority=2, frequency=3,
         default_action="WHATSAPP", active=True, template_message="""Oi, {NOME}! 🙂
Aqui é do Financeiro Portal Móveis💙

📌 Lembrete
{PARCELAS}

Total em aberto: {TOTAL}

Se você já pagou, desconsidere. ✅
Se quiser, me peça que eu envio PIX/2ª via agora. 💳

🤝 Estou à disposição pra te ajudar no que precisar.
📲 Retorno: (67) 99916-1881 | (67) 99656-9698"""),

    dict(level="MODERADA", start_days=7, end_days=14, priority=3, frequency=7,
         default_action="WHATSAPP", active=True, template_message="""Bom dia, {NOME}! 👋
Aqui é do Financeiro Portal Móveis💙

📌 Confirmação de pagamento
{PARCELAS}

Total em aberto: {TOTAL}

Você prefere receber PIX ou boleto/2ª via por aqui? ✅

💙 Pode contar comigo se precisar.
📲 Retorno: (67) 99916-1881 | (67) 99656-9698"""),

    dict(level="MODERADA", start_days=15, end_days=24, priority=4, frequency=5,
         default_action="WHATSAPP", active=True, template_message="""Boa tarde, {NOME}! 🙂
Aqui é do Financeiro Portal Móveis💙

⚠️ Regularização
{PARCELAS}

Total em aberto: {TOTAL}

Por favor, me informe: você consegue pagar hoje ou qual data você consegue pagar, pra eu registrar aqui. ✅

✅ Assim que me confirmar, eu já organizo tudo por aqui.
📲 Retorno: (67) 99916-1881 | (67) 99656-9698"""),

    dict(level="MODERADA", start_days=25, end_days=89, priority=5, frequency=5,
         default_action="WHATSAPP", active=True, template_message="""Oi, {NOME}! Tudo certo?
Aqui é do Financeiro Portal Móveis💙

⚠️ Aviso importante
{PARCELAS}

Total em aberto: {TOTAL}

Precisamos resolver o quanto antes para evitar avanço no processo de cobrança.
Me confirme a data do pagamento ou me peça PIX/2ª via. ✅

🤝 Me chama aqui que eu te ajudo a finalizar isso.
📲 Retorno: (67) 99916-1881 | (67) 99656-9698"""),

    # ── INTENSA ───────────────────────────────────────────────────────────────
    dict(level="INTENSA", start_days=-3, end_days=-1, priority=1, frequency=0,
         default_action="WHATSAPP", active=True, template_message="""Olá, {NOME}! 😊
Aqui é do Financeiro Portal Móveis💙

📅 Passando pra avisar que sua parcela vence em breve:
{PARCELAS_FUTURAS}

Estamos à disposição! Evite atrasos. ✅

📲 Retorno: (67) 99916-1881 | (67) 99656-9698"""),

    dict(level="INTENSA", start_days=0, end_days=2, priority=3, frequency=0,
         default_action="WHATSAPP", active=True, template_message="""Bom dia, {NOME}! 👋
Aqui é do Financeiro Portal Móveis💙

🗓️ Vence hoje
{PARCELAS}

Total em aberto: {TOTAL}

Se precisar, posso enviar PIX/2ª via agora. ✅

📌 Me avise por aqui se precisar de algo.
📲 Retorno: (67) 99916-1881 | (67) 99656-9698"""),

    dict(level="INTENSA", start_days=7, end_days=14, priority=5, frequency=7,
         default_action="WHATSAPP", active=True, template_message="""Olá, {NOME}! 👋
Aqui é do Financeiro Portal Móveis💙

⚠️ Confirmação necessária
{PARCELAS}

Total em aberto: {TOTAL}

Por favor, responda: você paga hoje ou qual data para pagamento? ✅

📌 Aguardo sua confirmação.
📲 Retorno: (67) 99916-1881 | (67) 99656-9698"""),

    dict(level="INTENSA", start_days=15, end_days=19, priority=6, frequency=5,
         default_action="WHATSAPP", active=True, template_message="""Oi, {NOME}.
Aqui é do Financeiro Portal Móveis💙

⚠️ Pendência em aberto
{PARCELAS}

Total em aberto: {TOTAL}

Precisamos regularizar. Me confirme: pagamento hoje ou data combinada. ✅
Se precisar, envio PIX/2ª via imediatamente.

✅ Assim que confirmar, eu já encerro por aqui.
📲 Retorno: (67) 99916-1881 | (67) 99656-9698"""),

    dict(level="INTENSA", start_days=25, end_days=29, priority=8, frequency=5,
         default_action="WHATSAPP", active=True, template_message="""Boa tarde, {NOME}.
Aqui é do Financeiro Portal Móveis💙

⚠️ Aviso de encaminhamento
{PARCELAS}

Total em aberto: {TOTAL}

Se não houver regularização, poderá ser encaminhada para o próximo nível de cobrança.
Me confirme hoje o pagamento ou a data exata. ✅

📌 Preciso do seu retorno para prosseguir.
📲 Retorno: (67) 99916-1881 | (67) 99656-9698"""),

    dict(level="INTENSA", start_days=30, end_days=9999, priority=9, frequency=7,
         default_action="WHATSAPP", active=True, template_message="""Olá, {NOME}.
Aqui é do Financeiro Portal Móveis💙

⚠️ Aviso final desta etapa
{PARCELAS}

Total em aberto: {TOTAL}

Preciso que você regularize hoje ou confirme uma data imediata.
Caso contrário, seguirá para tratativa de cobrança avançada. ✅

📌 Aguardo seu retorno ainda hoje.
📲 Retorno: (67) 99916-1881 | (67) 99656-9698"""),
]

if __name__ == "__main__":
    db = SessionLocal()
    existing = db.query(CollectionRule).count()

    if existing > 0:
        print(f"Regras ja existem ({existing}). Limpando e reinserindo...")
        db.query(CollectionRule).delete()
        db.commit()

    for r in RULES:
        db.add(CollectionRule(**r))

    db.commit()
    total = db.query(CollectionRule).count()
    db.close()
    print(f"Seed concluido: {total} regras inseridas.")
