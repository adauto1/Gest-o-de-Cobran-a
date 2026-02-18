from app.main import SessionLocal, Customer, Installment, days_overdue, rule_for_overdue
from datetime import date

def audit():
    db = SessionLocal()
    # IDs de interesse: 2 (Fernanda), e vamos buscar a Secretaria
    targets = [2]
    sec = db.query(Customer).filter(Customer.name.like("%SECRETARIA%")).first()
    if sec: targets.append(sec.id)
    
    for cid in targets:
        c = db.query(Customer).get(cid)
        print(f"\n=== Auditoria: {c.name} (ID: {c.id}) ===")
        
        # 1. Parcelas no Banco
        all_insts = db.query(Installment).filter(Installment.customer_id == cid).all()
        print(f"Total de parcelas no DB: {len(all_insts)}")
        for i in all_insts:
             print(f"  ID: {i.id} | Status: '{i.status}' | Venc: {i.due_date}")
        
        # 2. Simular Filtro do main.py
        filtered = sorted(
            [i for i in all_insts if i.status in ("VENCIDA", "EM ABERTO", "ABERTA")],
            key=lambda x: x.due_date
        )
        print(f"Parcelas que passam no filtro: {len(filtered)}")
        
        if filtered:
            first = filtered[0]
            days = days_overdue(first.due_date)
            print(f"Dias de atraso calculados: {days}")
            
            rule = rule_for_overdue(db, days)
            if rule:
                print(f"SUCESSO: Regra matched ID {rule.id} ({rule.start_days} a {rule.end_days})")
            else:
                print("FALHA: Nenhuma regra encontrada para esses dias.")
                # Listar regras ativas para ver o que tem
                from app.main import CollectionRule
                active_rules = db.query(CollectionRule).filter(CollectionRule.active == True).all()
                print(f"Regras ativas no sistema: {[ (r.id, r.start_days, r.end_days) for r in active_rules ]}")
        else:
            print("FALHA: Nenhuma parcela em aberto encontrada (filtro falhou).")
            
    db.close()

if __name__ == "__main__":
    audit()
