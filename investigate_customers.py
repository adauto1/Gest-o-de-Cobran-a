import os
import sys
from datetime import date, datetime

# Adiciona o diretório atual ao path para encontrar o app
sys.path.append(os.getcwd())

from app.main import SessionLocal, Customer, Installment, CollectionRule

def investigate():
    db = SessionLocal()
    try:
        print("--- INVESTIGAÇÃO DE CLIENTES COM TELEFONE ---")
        
        # 1. Localizar clientes com telefone
        customers = db.query(Customer).filter(Customer.whatsapp != None, Customer.whatsapp != "").all()
        print(f"Clientes com telefone encontrados: {len(customers)}")
        
        today = date.today()
        print(f"Data de hoje: {today}")
        
        for c in customers:
            print(f"\nCliente: {c.name} (ID: {c.id})")
            print(f"  WhatsApp: {c.whatsapp}")
            print(f"  Perfil: {c.profile_cobranca}")
            
            # Parcelas
            insts = db.query(Installment).filter(Installment.customer_id == c.id, Installment.status == "ABERTA").all()
            print(f"  Parcelas em aberto: {len(insts)}")
            for i in insts:
                delay = (today - i.due_date).days
                print(f"    - Vencimento: {i.due_date} | Valor: {i.open_amount} | Atraso: {delay} dias")
                
        # 2. Verificar Regras ativas
        rules = db.query(CollectionRule).filter(CollectionRule.active == True).all()
        print(f"\n--- REGRAS ATIVAS ({len(rules)}) ---")
        for r in rules:
            print(f"  [{r.level}] D{r.start_days} até D{r.end_days} | Freq: {r.frequency} dias")
            
    finally:
        db.close()

if __name__ == "__main__":
    investigate()
