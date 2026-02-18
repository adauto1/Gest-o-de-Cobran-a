from app.main import SessionLocal, Customer, days_overdue, rule_for_overdue, format_money
from datetime import date, datetime
from decimal import Decimal

def debug_fernanda():
    db = SessionLocal()
    cliente_id = 2 # Fernanda
    cliente = db.query(Customer).filter(Customer.id == cliente_id).first()
    
    print(f"DEBUG: Cliente: {cliente.name}")
    
    insts = sorted(
        [i for i in cliente.installments if i.status in ("VENCIDA", "EM ABERTO", "ABERTA")],
        key=lambda x: x.due_date
    )
    
    print(f"DEBUG: Parcelas filtradas: {[ (i.id, i.status, i.due_date) for i in insts]}")
    
    if not insts:
        print("DEBUG: Caiu no block 'if not insts'")
        return

    total_open = sum(i.amount for i in insts)
    max_overdue = days_overdue(insts[0].due_date)
    print(f"DEBUG: max_overdue calculado: {max_overdue}")
    
    matched_rule = rule_for_overdue(db, max_overdue)
    
    if not matched_rule:
        print("DEBUG: 'matched_rule' é None")
        
        # Por curiosidade, vamos ver todas as regras ativas
        from app.main import CollectionRule
        rules = db.query(CollectionRule).filter(CollectionRule.active == True).all()
        print(f"DEBUG: Total de regras ativas: {len(rules)}")
        for r in rules:
            if r.start_days <= max_overdue <= r.end_days:
                 print(f"DEBUG: ENCONTREI UM MATCH MANUALMENTE: ID {r.id} ({r.start_days} a {r.end_days})")
            else:
                 # print(f"DEBUG: Regra {r.id} ({r.start_days} a {r.end_days}) não serve")
                 pass
    else:
        print(f"DEBUG: Rule matched! ID {matched_rule.id} ({matched_rule.start_days} a {matched_rule.end_days})")
        print(f"DEBUG: Template: {matched_rule.template_message[:50]}...")

    db.close()

if __name__ == "__main__":
    debug_fernanda()
