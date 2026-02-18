import sqlite3
from datetime import datetime

DB_PATH = "./data/app.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("=" * 70)
print("VERIFICAÇÃO: Parcelas do Cliente TESTE")
print("=" * 70)

# Busca cliente TESTE
cursor.execute("SELECT id, name, external_key FROM customers WHERE name LIKE '%TESTE%'")
customers = cursor.fetchall()

if not customers:
    print("\n❌ Cliente TESTE não encontrado no banco!")
else:
    for cust_id, name, ext_key in customers:
        print(f"\n✅ Cliente encontrado:")
        print(f"   ID: {cust_id}")
        print(f"   Nome: {name}")
        print(f"   External Key: {ext_key}")
        
        # Busca parcelas deste cliente
        cursor.execute("""
            SELECT id, due_date, amount, open_amount, status, paid_at, created_at
            FROM installments
            WHERE customer_id = ?
            ORDER BY due_date DESC
        """, (cust_id,))
        
        installments = cursor.fetchall()
        
        if not installments:
            print(f"\n   ⚠️  Nenhuma parcela encontrada para este cliente")
        else:
            print(f"\n   📋 Parcelas ({len(installments)}):")
            for inst_id, due, amt, open_amt, status, paid_at, created in installments:
                print(f"\n   Parcela #{inst_id}:")
                print(f"      Vencimento: {due}")
                print(f"      Valor Total: R$ {amt:,.2f}")
                print(f"      Valor Aberto: R$ {open_amt:,.2f}")
                print(f"      Status: {status}")
                print(f"      Pago em: {paid_at if paid_at else 'N/A'}")
                print(f"      Criado em: {created}")
                
                if status == "PAGA" and amt >= 12000:
                    print(f"      🎉 SUCESSO! Parcela de R$ 12k foi marcada como PAGA!")

conn.close()

print("\n" + "=" * 70)
