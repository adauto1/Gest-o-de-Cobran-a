import sqlite3

def check():
    conn = sqlite3.connect('./data/app.db')
    c = conn.cursor()
    
    print("--- Schema: customers ---")
    for row in c.execute("PRAGMA table_info(customers)"):
        print(row)
        
    print("\n--- Schema: installments ---")
    cols = []
    for row in c.execute("PRAGMA table_info(installments)"):
        print(row)
        cols.append(row[1])
        
    print("\n")
    if 'total_amount' in cols:
        s = c.execute("SELECT sum(total_amount) FROM installments").fetchone()[0]
        print(f"Total Amount Sum: {s}")
    else:
        print("Column 'total_amount' not found!")
        
    conn.close()

if __name__ == '__main__':
    check()
