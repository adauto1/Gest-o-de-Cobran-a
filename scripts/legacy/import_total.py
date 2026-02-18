import os
import re
from datetime import datetime
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, Column, Integer, String, Date, DateTime, Float, ForeignKey, text
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. Configuração do Banco (Conexão existente)
DB_PATH = "./data/app.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 2. Definição do Schema
class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    whatsapp = Column(String)
    store = Column(String)

class Installment(Base):
    __tablename__ = "installments"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    due_date = Column(Date)
    total_amount = Column(Float)
    open_amount = Column(Float)
    status = Column(String)
    last_update = Column(DateTime)

# 3. Limpeza das Tabelas via SQL (Funciona com banco aberto)
def clean_database():
    db = SessionLocal()
    try:
        print("Limpando dados antigos...")
        db.execute(text("DELETE FROM installments"))
        db.execute(text("DELETE FROM customers"))
        db.commit()
        print("Tabelas limpas para carga total.")
    except Exception as e:
        print(f"Erro ao limpar: {e}")
        db.rollback()
    finally:
        db.close()

# 4. Parsing
def parse_infocommerce_html(file_path):
    print(f"Lendo: {file_path}")
    with open(file_path, 'r', encoding='latin-1', errors='ignore') as f:
        soup = BeautifulSoup(f, 'lxml')
    
    tags = soup.find_all(['div', 'p', 'span'])
    rows_data = {}
    for tag in tags:
        style = tag.get('style', '')
        top_match = re.search(r'top:(\d+)px', style)
        left_match = re.search(r'left:(\d+)px', style)
        text_content = tag.get_text().strip()
        if top_match and left_match and text_content:
            top = int(top_match.group(1))
            if top not in rows_data: rows_data[top] = []
            rows_data[top].append({'left': int(left_match.group(1)), 'text': text_content})
    
    parsed_titles = []
    for top in sorted(rows_data.keys()):
        line_dict = {el['left']: el['text'] for el in rows_data[top]}
        emissao = line_dict.get(54)
        vencimento = line_dict.get(588)
        cliente = line_dict.get(264)
        valor_raw = line_dict.get(648)
        if emissao and vencimento and re.match(r'\d{2}/\d{2}/\d{4}', emissao) and re.match(r'\d{2}/\d{2}/\d{4}', vencimento):
            if valor_raw:
                try:
                    v_str = valor_raw.replace('.', '').replace(',', '.')
                    parsed_titles.append({
                        'vencimento': vencimento,
                        'cliente': cliente or "DESCONHECIDO",
                        'valor': float(v_str)
                    })
                except: continue
    return parsed_titles

# 5. Carga
def import_total(parsed_data):
    db = SessionLocal()
    try:
        print(f"Iniciando carga de {len(parsed_data)} títulos...")
        customers_cache = {}
        count_cust = 0
        count_inst = 0
        
        for item in parsed_data:
            name = item['cliente']
            if name not in customers_cache:
                customer = Customer(name=name, whatsapp="", store="LOJA 1")
                db.add(customer)
                db.flush()
                customers_cache[name] = customer.id
                count_cust += 1
            
            due_dt = datetime.strptime(item['vencimento'], '%d/%m/%Y').date()
            inst = Installment(
                customer_id=customers_cache[name],
                due_date=due_dt,
                total_amount=item['valor'],
                open_amount=item['valor'],
                status="ABERTO",
                last_update=datetime.now()
            )
            db.add(inst)
            count_inst += 1
            if count_inst % 1000 == 0:
                print(f"Processando... {count_inst}")
                db.commit()

        db.commit()
        print("-" * 50)
        print(f"IMPORTAÇÃO HTML CONCLUÍDA!")
        print(f"Clientes: {count_cust} | Títulos: {count_inst}")
        print("-" * 50)
    finally:
        db.close()

if __name__ == "__main__":
    html_file = "relatorio.htm"
    if os.path.exists(html_file):
        clean_database()
        data = parse_infocommerce_html(html_file)
        if data:
            import_total(data)
    else:
        print("Arquivo relatorio.htm nao encontrado.")
