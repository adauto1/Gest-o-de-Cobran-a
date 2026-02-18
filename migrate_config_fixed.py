import sqlite3
import os

def migrate_db():
    db_path = os.path.join("data", "app.db")
    if not os.path.exists(db_path):
        print(f"Erro: Banco de dados nao encontrado em {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Tenta adicionar a coluna whatsapp_instancia
        try:
            cursor.execute("ALTER TABLE configuracoes ADD COLUMN whatsapp_instancia VARCHAR(100)")
            print("Coluna whatsapp_instancia adicionada em data/app.db.")
        except sqlite3.OperationalError:
            print("Coluna whatsapp_instancia ja existe.")
            
        # Tenta adicionar a coluna whatsapp_token
        try:
            cursor.execute("ALTER TABLE configuracoes ADD COLUMN whatsapp_token VARCHAR(100)")
            print("Coluna whatsapp_token adicionada em data/app.db.")
        except sqlite3.OperationalError:
            print("Coluna whatsapp_token ja existe.")
            
        conn.commit()
    except Exception as e:
        print(f"Erro na migracao: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_db()
