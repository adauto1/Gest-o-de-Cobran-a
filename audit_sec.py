from app.main import SessionLocal, Customer, Installment, days_overdue, rule_for_overdue

def audit_sec():
    db = SessionLocal()
    c = db.query(Customer).filter(Customer.name.like("%SECRETARIA%")).first()
    if not c:
        print("Secretaria não encontrada")
        return
    
    print(f"--- {c.name} ---")
    insts = db.query(Installment).filter(Installment.customer_id == c.id).all()
    print(f"Total: {len(insts)}")
    valid = [i for i in insts if i.status in ("VENCIDA", "EM ABERTO", "ABERTA")]
    print(f"Em aberto (filtro): {len(valid)}")
    
    for i in valid:
        print(f"  ID: {i.id} | Status: {i.status} | Venc: {i.due_date}")
        
    if valid:
        days = days_overdue(valid[0].due_date)
        print(f"Dias atraso: {days}")
        rule = rule_for_overdue(db, days)
        print(f"Rule Matched: {rule.id if rule else 'NONE'}")
    
    db.close()

if __name__ == "__main__":
    audit_sec()
