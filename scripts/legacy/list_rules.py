from app.main import SessionLocal, CollectionRule

def list_rules():
    db = SessionLocal()
    rules = db.query(CollectionRule).order_by(CollectionRule.level, CollectionRule.start_days).all()
    
    with open("rules_dump.txt", "w", encoding="utf-8") as f:
        f.write("--- Regras Ativas ---\n")
        current_level = None
        for r in rules:
            if r.level != current_level:
                f.write(f"\n[{r.level}]\n")
                current_level = r.level
            
            tipo = "Atraso"
            if r.start_days < 0: tipo = "Preventiva"
            elif r.start_days == 0: tipo = "Vencimento"
            
            dias = f"{abs(r.start_days)} dias"
            if r.start_days == 0: dias = "Hoje"
            
            template = r.template_message.replace(chr(10), ' ')[:50]
            f.write(f"- {tipo} ({dias}): {template}...\n")
            f.write(f"  Freq: a cada {r.frequency} dias\n")
        # print(f"  Msg: {r.template_message[:50]}...")

if __name__ == "__main__":
    list_rules()
