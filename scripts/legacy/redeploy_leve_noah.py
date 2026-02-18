from app.main import SessionLocal, CollectionRule

def redeploy_leve_noah():
    db = SessionLocal()
    try:
        # 1. Inativar regras LEVE atuais para limpeza total
        db.query(CollectionRule).filter(CollectionRule.level == "LEVE").update({"active": False})
        
        # 2. Definir os novos templates EXATOS solicitados pelo usuário
        noah_templates = [
            # D+3 (3 a 6 dias)
            {
                "start": 3, "end": 6, "priority": 1, "freq": 3,
                "msg": "Olá, *{nome}*! 😊\n\nAqui é o *Noah*, do financeiro da *Portal Móveis*!\n\nPassando para lembrar que identificamos uma parcela em aberto:\n\n💰 *Valor:* R$ {valor}\n📅 *Venceu em:* {data_vencimento}\n\nCaso já tenha pago, pode desconsiderar! 🙏\n\nQualquer dúvida, é só me chamar:\n📞 *67 9 9853-9477*\n📞 *67 9 9656-9698*\n🕐 Seg a Sex, 8h às 18h | Sáb, 8h às 12h\n\n_Noah — Financeiro Portal Móveis_ 🏠"
            },
            # D+7 (7 a 14 dias)
            {
                "start": 7, "end": 14, "priority": 2, "freq": 7,
                "msg": "Oi, *{nome}*! 👋\n\nAqui é o *Noah*, do financeiro da *Portal Móveis* novamente!\n\nSua parcela ainda consta em aberto:\n\n💰 *Valor:* R$ {valor}\n📅 *Vencimento:* {data_vencimento}\n⏳ *Dias em atraso:* 7 dias\n\nSabemos que o dia a dia é corrido! Se precisar negociar um prazo, é só me chamar:\n\n📞 *67 9 9853-9477*\n📞 *67 9 9656-9698*\n🕐 Seg a Sex, 8h às 18h | Sáb, 8h às 12h\n\n_Noah — Financeiro Portal Móveis_"
            },
            # D+15 (15 a 24 dias)
            {
                "start": 15, "end": 24, "priority": 3, "freq": 15,
                "msg": "Olá, *{nome}*.\n\nAqui é o *Noah*, do financeiro da *Portal Móveis*.\n\nSua parcela ainda não foi regularizada:\n\n💰 *Valor:* R$ {valor}\n📅 *Vencimento:* {data_vencimento}\n⏳ *Dias em atraso:* 15 dias\n\nEstamos à disposição para encontrar a melhor solução para você. Entre em contato e veja as opções disponíveis:\n\n📞 *67 9 9853-9477*\n📞 *67 9 9656-9698*\n🕐 Seg a Sex, 8h às 18h | Sáb, 8h às 12h\n\n_Noah — Financeiro Portal Móveis_ ✅"
            },
            # D+25 (25 a 29 dias)
            {
                "start": 25, "end": 29, "priority": 4, "freq": 25,
                "msg": "*{nome}*, tudo bem?\n\nAqui é o *Noah*, do financeiro da *Portal Móveis*.\n\nSua parcela está há *25 dias* em atraso e ainda não identificamos a regularização:\n\n💰 *Valor:* R$ {valor}\n📅 *Vencimento:* {data_vencimento}\n\nVamos resolver isso juntos! Entre em contato ainda hoje 👇\n\n📞 *67 9 9853-9477*\n📞 *67 9 9656-9698*\n🕐 Seg a Sex, 8h às 18h | Sáb, 8h às 12h\n\n_Noah — Financeiro Portal Móveis_"
            }
        ]
        
        for t in noah_templates:
            rule = CollectionRule(
                level="LEVE",
                start_days=t["start"],
                end_days=t["end"],
                template_message=t["msg"],
                priority=t["priority"],
                frequency=t["freq"],
                active=True
            )
            db.add(rule)
            
        db.commit()
        print("Régua LEVE (Noah) REIMPLANTADA com sucesso!")
    except Exception as e:
        db.rollback()
        print(f"Erro na reimplantação: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    redeploy_leve_noah()
