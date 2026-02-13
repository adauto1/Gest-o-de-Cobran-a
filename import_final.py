import os
import re
from datetime import datetime
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, text

# 1. Conexão Minimalista
DB_PATH = "./data/app.db"
engine = create_engine(f"sqlite:///{DB_PATH}")

def clean_database():
    print("Limpando banco de dados (SQL Bruto)...")
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM installments"))
        conn.execute(text("DELETE FROM customers"))
        conn.commit()
    print("Banco limpo.")

def parse_infocommerce_html(file_path):
    print(f"Lendo HTML: {file_path}")
    with open(file_path, 'r', encoding='latin-1', errors='ignore') as f:
        soup = BeautifulSoup(f, 'lxml')
    
    tags = soup.find_all(['div', 'p', 'span'])
    rows_data = {}
    for tag in tags:
        style = tag.get('style', '')
        top_match = re.search(r'top:(\d+)px', style)
        left_match = re.search(r'left:(\d+)px', style)
        txt = tag.get_text().strip()
        if top_match and left_match and txt:
            top = int(top_match.group(1))
            if top not in rows_data: rows_data[top] = {}
            rows_data[top][int(left_match.group(1))] = txt
    
    parsed = []
    for top in sorted(rows_data.keys()):
        row = rows_data[top]
        emissao = row.get(54)
        cliente = row.get(264)
        vencimento = row.get(588)
        valor_raw = row.get(648)
        
        if emissao and vencimento and re.match(r'\d{2}/\d{2}/\d{4}', emissao) and re.match(r'\d{2}/\d{2}/\d{4}', vencimento):
            if valor_raw:
                try:
                    v_str = valor_raw.replace('.', '').replace(',', '.')
                    parsed.append({
                        'vencimento': datetime.strptime(vencimento, '%d/%m/%Y').date(),
                        'cliente': (cliente or "DESCONHECIDO").upper(),
                        'valor': float(v_str)
                    })
                except: continue
    return parsed

def import_fast(data):
    print(f"Iniciando carga rápida de {len(data)} títulos...")
    
    with engine.connect() as conn:
        customers_cache = {}
        # Garante que clientes na DB estão no cache se sobrar algum (apesar do clean)
        res = conn.execute(text("SELECT name, id FROM customers"))
        for r in res: customers_cache[r[0]] = r[1]
        
        count_inst = 0
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        for item in data:
            # Cliente
            if item['cliente'] not in customers_cache:
                conn.execute(
                    text("INSERT INTO customers (name, whatsapp, store) VALUES (:n, '', 'LOJA 1')"),
                    {"n": item['cliente']}
                )
                cid = conn.execute(text("SELECT last_insert_rowid()")).scalar()
                customers_cache[item['cliente']] = cid
            
            # Parcela
            conn.execute(
                text("""INSERT INTO installments 
                     (customer_id, due_date, total_amount, open_amount, status, last_update) 
                     VALUES (:cid, :due, :amt, :amt, 'ABERTO', :now)"""),
                {
                    "cid": customers_cache[item['cliente']],
                    "due": item['vencimento'],
                    "amt": item['valor'],
                    "now": now
                }
            )
            count_inst += 1
            if count_inst % 1000 == 0:
                print(f"Inseridos: {count_inst}")
        
        conn.commit()
    print(f"CARGA CONCLUÍDA! Total de Títulos: {count_inst}")

if __name__ == "__main__":
    file = "relatorio.htm"
    if os.path.exists(file):
        clean_database()
        data = parse_infocommerce_html(file)
        if data:
            import_fast(data)
    else:
        print("Arquivo relatorio.htm nao encontrado.")
