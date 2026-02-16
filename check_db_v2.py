import os
import sys

# Add current dir to path to find app
sys.path.append(os.getcwd())

from app.main import SessionLocal, Configuracoes, Installment

db = SessionLocal()
try:
    c = db.query(Configuracoes).first()
    count = db.query(Installment).filter(Installment.status == "ABERTA").count()
    print(f"WhatsApp Ativo: {c.whatsapp_ativo if c else 'None'}")
    print(f"Modo Teste: {c.whatsapp_modo_teste if c else 'None'}")
    print(f"Open Installments: {count}")
    
    # Check if there are any MessageDispatchLogs from today
    from app.main import MessageDispatchLog
    import datetime
    today = datetime.date.today()
    log_count = db.query(MessageDispatchLog).filter(MessageDispatchLog.created_at >= datetime.datetime.combine(today, datetime.time.min)).count()
    print(f"Logs Today: {log_count}")
finally:
    db.close()
