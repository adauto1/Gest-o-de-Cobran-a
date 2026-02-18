import sqlite3

conn = sqlite3.connect('./data/app.db')
c = conn.cursor()

c.execute('SELECT COUNT(*) FROM installments WHERE status="PAGA"')
pagas = c.fetchone()[0]

c.execute('SELECT COUNT(*) FROM installments WHERE status="ABERTA"')
abertas = c.fetchone()[0]

print("Parcelas PAGAS:", pagas)
print("Parcelas ABERTAS:", abertas)

# Verifica se há parcelas do cliente TESTE
c.execute('SELECT COUNT(*) FROM customers WHERE name LIKE "%TESTE%"')
teste_count = c.fetchone()[0]
print("Clientes com TESTE no nome:", teste_count)

if teste_count > 0:
    c.execute('''
        SELECT i.status, COUNT(*) 
        FROM installments i
        JOIN customers c ON i.customer_id = c.id
        WHERE c.name LIKE "%TESTE%"
        GROUP BY i.status
    ''')
    print("\nParcelas do cliente TESTE:")
    for status, count in c.fetchall():
        print(f"  {status}: {count}")

conn.close()
