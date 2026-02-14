
import sys
import os

# Ensure app module can be found
sys.path.append(os.getcwd())

from app.main import SessionLocal, Customer, Installment, CollectionAction, SentMessage

def reset_data():
    db = SessionLocal()
    print("Iniciando limpeza de dados...")
    try:
        # Delete dependent tables first
        deleted_actions = db.query(CollectionAction).delete()
        print(f"- Ações removidas: {deleted_actions}")
        
        deleted_msgs = db.query(SentMessage).delete()
        print(f"- Mensagens removidas: {deleted_msgs}")
        
        deleted_inst = db.query(Installment).delete()
        print(f"- Parcelas removidas: {deleted_inst}")
        
        deleted_cust = db.query(Customer).delete()
        print(f"- Clientes removidos: {deleted_cust}")
        
        db.commit()
        print("Limpeza concluída com sucesso!")
    except Exception as e:
        print(f"Erro durante a limpeza: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    reset_data()
