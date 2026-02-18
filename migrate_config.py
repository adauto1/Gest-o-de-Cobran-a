import sqlite3

def migrate_db():
    conn = sqlite3.connect("cobranca.db")
    cursor = conn.cursor()
    
    try:
        # Tenta adicionar a coluna whatsapp_instancia
        try:
            cursor.execute("ALTER TABLE configuracoes ADD COLUMN whatsapp_instancia VARCHAR(100)")
            print("Coluna whatsapp_instancia adicionada.")
        except sqlite3.OperationalError:
            print("Coluna whatsapp_instancia ja existe.")
            
        # Tenta adicionar a coluna whatsapp_token
        try:
            cursor.execute("ALTER TABLE configuracoes ADD COLUMN whatsapp_token VARCHAR(100)")
            print("Coluna whatsapp_token adicionada.")
        except sqlite3.OperationalError:
            print("Coluna whatsapp_token ja existe.")
            
        conn.commit()
    except Exception as e:
        print(f"Erro na migracao: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_db()
