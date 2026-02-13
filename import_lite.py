import os
import re
import sqlite3
from datetime import datetime
from bs4 import BeautifulSoup

DB_PATH = "./data/app.db"
HTML_PATH = "relatorio.htm"

def clean_date(text):
    if not text: return None
    match = re.search(r'^(\d{2}/\d{2}/\d{4})$', text.strip())
    return match.group(1) if match else None

def is_valid_client(name):
    if not name or len(name) < 4: return False
    if re.match(r'^\d', name): return False
    name_up = name.upper()
    forbidden = ["PAGINA", "EMISSAO", "LISTAGEM", "ORDEM", "CONTRATO", "VALOR TOTAL", "RECEBER", "COLISEU"]
    if any(f in name_up for f in forbidden): return False
    # Nomes com muitas datas não costumam ser de clientes
    if len(re.findall(r'\d{2}/\d{2}/\d{4}', name)) > 0: return False
    return True

def parse_infocommerce():
    print(f"Sincronização de Precisão: {HTML_PATH}")
    if not os.path.exists(HTML_PATH): return []

    with open(HTML_PATH, 'r', encoding='latin-1', errors='ignore') as f:
        soup = BeautifulSoup(f, 'lxml')
    
    rows_data = {}
    for tag in soup.find_all(['div', 'p', 'span']):
        style = tag.get('style', '')
        top_match = re.search(r'top:(\d+)px', style)
        left_match = re.search(r'left:(\d+)px', style)
        txt = tag.get_text().strip()
        if top_match and left_match and txt:
            t, l = int(top_match.group(1)), int(left_match.group(1))
            if t not in rows_data: rows_data[t] = {}
            if l in rows_data[t]: rows_data[t][l] += " " + txt
            else: rows_data[t][l] = txt
    
    data = []
    seen_keys = set()
    total_val = 0.0
    
    for t in sorted(rows_data.keys()):
        r = rows_data[t]
        
        line_text = " ".join(r.values()).upper()
        if any(x in line_text for x in ["VALOR TOTAL", "TOTAL GERAL", "SUB-TOTAL"]):
            continue

        emissao_raw = r.get(54)
        doc_raw = r.get(132, "0") # Numero do Documento
        vencimento_raw = r.get(588)
        cliente_raw = r.get(264, "").strip()
        valor_raw = r.get(648)
        
        em_l = clean_date(emissao_raw)
        ve_l = clean_date(vencimento_raw)
        
        if em_l and ve_l and is_valid_client(cliente_raw):
            if valor_raw:
                try:
                    v_str = re.sub(r'[^\d,.]', '', valor_raw)
                    v_str = v_str.replace('.', '').replace(',', '.')
                    val = float(v_str)
                    
                    # Chave de unicidade incluindo Documento (L132) + Cliente + Vencimento + Valor
                    # Isso permite que o mesmo cliente tenha duas parcelas iguais no mesmo dia se tiverem docs diferentes
                    # Ou se for o mesmo doc, mas em um top diferente, ele ignora se ja vimos essa combinacao
                    key = (doc_raw, cliente_raw.upper(), ve_l, val)
                    if key in seen_keys: continue
                    seen_keys.add(key)
                    
                    data.append({
                        'issue_date': datetime.strptime(em_l, '%d/%m/%Y').strftime('%Y-%m-%d'),
                        'due_date': datetime.strptime(ve_l, '%d/%m/%Y').strftime('%Y-%m-%d'),
                        'cliente': cliente_raw.upper()[:190],
                        'doc_id': doc_raw,
                        'amount': val
                    })
                    total_val += val
                except: continue
                
    print(f"VALOR TOTAL CALCULADO: R$ {total_val:,.2f}")
    print(f"TOTAL DE TITULOS: {len(data)}")
    return data

def import_sql(data):
    if not data: return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM installments")
        cursor.execute("DELETE FROM customers")
        customers_cache = {}
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        count = 0
        for item in data:
            name = item['cliente']
            if name not in customers_cache:
                ext_key = re.sub(r'[^A-Z0-9]', '', name)[:40] + str(count)
                cursor.execute("INSERT OR IGNORE INTO customers (name, external_key, store, created_at) VALUES (?, ?, 'LOJA 1', ?)", (name, ext_key, now))
                cursor.execute("SELECT id FROM customers WHERE name = ?", (name,))
                row = cursor.fetchone()
                if row: customers_cache[name] = row[0]
                else: 
                    cursor.execute("INSERT INTO customers (name, external_key, store) VALUES (?, ?, 'LOJA 1')", (name, ext_key))
                    customers_cache[name] = cursor.lastrowid
            
            cursor.execute("""
                INSERT INTO installments 
                (customer_id, contract_id, installment_number, issue_date, due_date, amount, open_amount, status, created_at) 
                VALUES (?, ?, ?, ?, ?, ?, ?, 'ABERTA', ?)
            """, (customers_cache[name], f"ERP-{item['doc_id']}-{count}", 1, item['issue_date'], item['due_date'], item['amount'], item['amount'], now))
            
            count += 1
            if count % 1000 == 0: conn.commit()
        conn.commit()
    finally:
        conn.close()

if __name__ == "__main__":
    recs = parse_infocommerce()
    if recs: import_sql(recs)
