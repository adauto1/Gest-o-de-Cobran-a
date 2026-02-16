import os
import sys
from datetime import date, datetime, timedelta

# Adiciona o diretório atual ao path para encontrar o app
sys.path.append(os.getcwd())

from app.main import SessionLocal, Customer, Installment, CollectionRule
from app.services.compliance import calcular_data_disparo

def simulate_diag():
    db = SessionLocal()
    try:
        with open("diag_final.txt", "w", encoding="utf-8") as f:
            today = date.today()
            f.write(f"DIAGNÓSTICO ESPECÍFICO - HOJE: {today} (Domingo)\n")
            
            customers = db.query(Customer).filter(Customer.whatsapp != None, Customer.whatsapp != "").all()
            for c in customers:
                f.write(f"\nCLIENTE: {c.name} (Perfil: {c.profile_cobranca})\n")
                insts = db.query(Installment).filter(Installment.customer_id == c.id, Installment.status == "ABERTA").all()
                if not insts:
                    f.write("  Sem parcelas abertas.\n")
                    continue
                    
                nearest_due = min(i.due_date for i in insts)
                
                rules = db.query(CollectionRule).filter(CollectionRule.active == True).all()
                for r in rules:
                    if r.start_days == r.end_days:
                        trigger_date = nearest_due + timedelta(days=r.start_days)
                        adjusted = calcular_data_disparo(nearest_due, r.start_days)
                        
                        f.write(f"  Regra {r.level} D{r.start_days}:\n")
                        f.write(f"    - Alvo Original: {trigger_date}\n")
                        f.write(f"    - Alvo Ajustado (Compliance): {adjusted.date()}\n")
                        if adjusted.date() == today:
                             f.write("    >>> MATCH PARA HOJE! <<<\n")
                        elif adjusted.date() == today + timedelta(days=1):
                             f.write("    >>> PROGRAMADO PARA AMANHÃ (Segunda) <<<\n")
                    else:
                        max_delay = max((today - i.due_date).days for i in insts)
                        if r.start_days <= max_delay <= r.end_days:
                            f.write(f"  Regra {r.level} FAIXA (D{r.start_days}-D{r.end_days}):\n")
                            f.write(f"    - Atraso Atual: {max_delay} dias\n")
                            f.write("    >>> MATCH FAIXA PARA HOJE! <<<\n")
    finally:
        db.close()

if __name__ == "__main__":
    simulate_diag()
