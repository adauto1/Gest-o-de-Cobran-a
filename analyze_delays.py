import os
import sys
from datetime import date, datetime

# Adiciona o diretório atual ao path para encontrar o app
sys.path.append(os.getcwd())

from app.main import SessionLocal, Customer, Installment, CollectionRule

def analyze():
    db = SessionLocal()
    try:
        today = date.today()
        print(f"DEBUG: Data de Hoje: {today}")
        
        customers = db.query(Customer).filter(Customer.whatsapp != None, Customer.whatsapp != "").all()
        for c in customers:
            print(f"\nCLIENTE: {c.name}")
            print(f"  Perfil: {c.profile_cobranca}")
            insts = db.query(Installment).filter(Installment.customer_id == c.id, Installment.status == "ABERTA").all()
            if not insts:
                print("  Nenhuma parcela em aberto.")
                continue
            
            # Calcular o perfil efetivo (caso seja automático)
            overdue_count = sum(1 for i in insts if (today - i.due_date).days > 0)
            effective_profile = c.profile_cobranca
            if effective_profile == "AUTOMATICO":
                if overdue_count >= 3: effective_profile = "INTENSA"
                elif overdue_count >= 2: effective_profile = "MODERADA"
                else: effective_profile = "LEVE"
            
            print(f"  Perfil Efetivo: {effective_profile}")
            print(f"  Parcelas Vencidas: {overdue_count}")
            
            # Mostrar atrasos
            for i in insts:
                delay = (today - i.due_date).days
                print(f"    - Vencimento: {i.due_date} | Atraso: {delay} dias")
                
            # Verificar se alguma regra bate
            rules = db.query(CollectionRule).filter(CollectionRule.active == True, CollectionRule.level == effective_profile).all()
            print(f"  Regras Aplicáveis ({effective_profile}):")
            for r in rules:
                is_match = False
                if r.start_days == r.end_days:
                    # Aqui entra a lógica de compliance que o scheduler usa... 
                    # Mas vamos simplificar o check inicial.
                    if r.start_days == (today - insts[0].due_date).days: # Simplificação
                        is_match = True
                else:
                    max_delay = max((today - i.due_date).days for i in insts)
                    if r.start_days <= max_delay <= r.end_days:
                        is_match = True
                print(f"    - {r.level} D{r.start_days} to D{r.end_days} | Match? {'SIM' if is_match else 'NÃO'}")

    finally:
        db.close()

if __name__ == "__main__":
    analyze()
