from app.main import SessionLocal, Customer, Installment, CollectionRule, today
from app.scheduler import run_collection_check
from datetime import timedelta
import logging

# Configura log para ver o output do scheduler
logging.basicConfig(level=logging.INFO)

def verify_profile():
    db = SessionLocal()
    print("--- Verificando Lógica de Perfil Manual ---")
    
    # 1. Criar Cliente Teste
    c = Customer(
        name="Cliente Perfil Teste",
        external_key="PERFIL_TESTE",
        profile_cobranca="INTENSA", # Forçando Intensa
        whatsapp="67999999999"
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    
    # 2. Criar Parcela Vencida (Dia do Vencimento)
    # Intensa tem regra para dia 0.
    t = today()
    i = Installment(
        customer_id=c.id,
        contract_id="TEST-PERFIL",
        installment_number=1,
        due_date=t, # Hoje
        amount=100,
        open_amount=100,
        status="ABERTA"
    )
    db.add(i)
    db.commit()
    
    # 3. Rodar Scheduler
    # A regra Intensa Dia 0 deve disparar.
    # Se fosse Automatico, talvez disparasse também.
    # Mas vamos garantir que ele filtrou.
    
    print(f"Cliente criado: ID {c.id}, Perfil: {c.profile_cobranca}")
    
    try:
        stats = run_collection_check(SessionLocal)
        print("Scheduler executado:", stats)
    except Exception as e:
        print(f"Erro no scheduler: {e}")
        
    # 4. Limpeza
    db.delete(i)
    db.delete(c)
    db.commit()
    print("Teste finalizado (verifique os logs acima se a mensagem foi 'criada').")

if __name__ == "__main__":
    verify_profile()
