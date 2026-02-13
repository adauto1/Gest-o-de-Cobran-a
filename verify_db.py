import sqlite3
import os

DB_PATH = "./data/app.db"

def verify():
    if not os.path.exists(DB_PATH):
        print("Banco não encontrado.")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT count(*) FROM customers")
    cust_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT count(*) FROM installments")
    inst_count = cursor.fetchone()[0]
    
    print("-" * 30)
    print(f"ESTADO DO BANCO DE DADOS:")
    print(f"Clientes: {cust_count}")
    print(f"Parcelas: {inst_count}")
    print("-" * 30)
    
    conn.close()

if __name__ == "__main__":
    verify()
