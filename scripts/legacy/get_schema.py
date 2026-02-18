import sqlite3
c = sqlite3.connect('./data/app.db')
cursor = c.cursor()
print("COLUMNS:")
for row in cursor.execute("PRAGMA table_info(installments)"):
    print(row[1])
c.close()
