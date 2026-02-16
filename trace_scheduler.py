import os
import sys
from datetime import date, datetime, timedelta
import json

# Adiciona o diretório atual ao path para encontrar o app
sys.path.append(os.getcwd())

from app.main import SessionLocal, Customer, Installment, CollectionRule, MessageDispatchLog, SentMessage, Configuracoes
from app.scheduler import run_collection_check

def trace_scheduler():
    db = SessionLocal()
    try:
        print("--- TRACE SCHEDULER ---")
        config = db.query(Configuracoes).first()
        print(f"WhatsApp Ativo: {config.whatsapp_ativo}")
        
        # Focar nos clientes com telefone
        customers = db.query(Customer).filter(Customer.whatsapp != None, Customer.whatsapp != "").all()
        
        for c in customers:
            print(f"\nVerificando Cliente: {c.name}")
            # Limpar logs de hoje para este cliente para forçar repetição se necessário
            today_start = datetime.combine(date.today(), datetime.min.time())
            db.query(MessageDispatchLog).filter(MessageDispatchLog.customer_id == c.id, MessageDispatchLog.created_at >= today_start).delete()
            db.commit()
            print(f"  Logs de hoje limpos para {c.name}")

        print("\nRodando scheduler (run_collection_check)...")
        stats = run_collection_check(SessionLocal)
        print(f"Resultados: {stats}")
        
        # Verificar o que foi criado
        logs = db.query(MessageDispatchLog).filter(MessageDispatchLog.created_at >= today_start).all()
        print(f"\nLogs criados após execução: {len(logs)}")
        for l in logs:
            print(f"  ID: {l.id} | Cliente: {l.customer_name} | Status: {l.status} | Reason: {l.compliance_block_reason}")

    finally:
        db.close()

if __name__ == "__main__":
    trace_scheduler()
