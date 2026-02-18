import os
import sys
from datetime import date, datetime

# Adiciona o diretório atual ao path para encontrar o app
sys.path.append(os.getcwd())

from app.main import SessionLocal, MessageDispatchLog

def check_errors():
    db = SessionLocal()
    try:
        today_start = datetime.combine(date.today(), datetime.min.time())
        log = db.query(MessageDispatchLog).filter(MessageDispatchLog.created_at >= today_start, MessageDispatchLog.status == "FAILED").first()
        if log:
            print(f"ID: {log.id}")
            print(f"Status: {log.status}")
            print(f"Error: {log.error}")
            # print(f"Full Metadata: {log.metadata}")
        else:
            print("Nenhum log de falha encontrado hoje.")
    finally:
        db.close()

if __name__ == "__main__":
    check_errors()
