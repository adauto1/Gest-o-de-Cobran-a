import os
import re
from decimal import Decimal
from datetime import datetime
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, Column, Integer, String, Date, DateTime, Numeric, Text, ForeignKey, Float
from sqlalchemy.orm import sessionmaker, declarative_base

# Configuração Direta
DATABASE_URL = "sqlite:///./data/app.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

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
    total_amount = Column(Float) # Mudado para Float para evitar erros de decimal em scripts simples
    open_amount = Column(Float)
    status = Column(String)
    last_update = Column(DateTime)

def parse_infocommerce_html(file_path):
    print(f"Relatório: {file_path}")
    with open(file_path, 'r', encoding='latin-1', errors='ignore') as f:
        soup = BeautifulSoup(f, 'lxml')
    
    tags = soup.find_all(['div', 'p', 'span'])
    rows_data = {}
    for tag in tags:
        style = tag.get('style', '')
        top_match = re.search(r'top:(\d+)px', style)
        left_match = re.search(r'left:(\d+)px', style)
        text = tag.get_text().strip()
        if top_match and left_match and text:
            top = int(top_match.group(1))
            if top not in rows_data: rows_data[top] = []
            rows_data[top].append({'left': int(left_match.group(1)), 'text': text})
    
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
                    v_float = float(v_str)
                    parsed_titles.append({
                        'vencimento': vencimento,
                        'cliente': cliente or "DESCONHECIDO",
                        'valor': v_float
                    })
                except: continue
    return parsed_titles

def import_to_db(parsed_data):
    db = SessionLocal()
    try:
        print(f"Importando {len(parsed_data)} títulos...")
        
        # Limpa dados anteriores ANTES da carga total
        db.query(Installment).delete()
        db.query(Customer).delete()
        db.commit()

        customers_cache = {}
        count_new_customers = 0
        count_new_inst = 0
        
        for item in parsed_data:
            name = item['cliente']
            if name not in customers_cache:
                customer = Customer(name=name, whatsapp="", store="LOJA 1")
                db.add(customer)
                db.flush()
                customers_cache[name] = customer.id
                count_new_customers += 1
            
            due_date = datetime.strptime(item['vencimento'], '%d/%m/%Y').date()
            
            inst = Installment(
                customer_id=customers_cache[name],
                due_date=due_date,
                total_amount=item['valor'],
                open_amount=item['valor'],
                status="ABERTO",
                last_update=datetime.now()
            )
            db.add(inst)
            count_new_inst += 1
            if count_new_inst % 1000 == 0:
                print(f"Processado: {count_new_inst}")
                db.commit() # Commit parcial para performance

        db.commit()
        print(f"FINALIZADO! Clientes: {count_new_customers} | Parcelas: {count_new_inst}")
    except Exception as e:
        print(f"ERRO: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    html_file = "relatorio.htm"
    if os.path.exists(html_file):
        data = parse_infocommerce_html(html_file)
        if data:
            import_to_db(data)
    else:
        print("Arquivo relatorio.htm nao encontrado.")
