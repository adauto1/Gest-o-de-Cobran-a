
import pandas as pd
from sqlalchemy.orm import Session
from datetime import datetime, date
import logging
import re
from ..main import Customer, Installment

def parse_date_html(val):
    if pd.isna(val): return None
    if isinstance(val, (datetime, date)): return val
    s = str(val).strip()
    # Try common formats
    for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]:
        try:
            return datetime.strptime(s, fmt).date()
        except:
            pass
    return None

def parse_money_html(val):
    if pd.isna(val): return 0.0
    if isinstance(val, (int, float)): return float(val)
    s = str(val).strip()
    s = s.replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(s)
    except:
        return 0.0

def process_html_import(file_content: bytes, db: Session, user_id: int):
    """
    Parses HTML report (InfoCommerce style)
    """
    try:
        # read_html returns list of DataFrames
        # we need to find the one with actual data
        dfs = pd.read_html(file_content, header=0, decimal=",", thousands=".")
    except Exception as e:
        return {"error": f"Erro ao ler HTML: {str(e)}"}

    df = None
    best_score = 0
    
    # Header keywords to look for
    keywords = ["cliente", "vencimento", "valor", "contrato", "cpf"]
    
    for d in dfs:
        score = 0
        cols = [str(c).lower() for c in d.columns]
        for k in keywords:
            if any(k in c for c in cols):
                score += 1
        
        if score > best_score and score >= 2: # At least 2 matches
            best_score = score
            df = d
            
    if df is None:
        return {"error": "Estrutura do HTML não reconhecida. Certifique-se que é o relatório correto."}

    # Normalize columns
    df.columns = [str(c).strip().lower().replace(" ", "_").replace("/", "_").replace(".", "") for c in df.columns]

    # Map known columns to standard
    # InfoCommerce: "Nome Cliente", "Vencto", "Valor", "Nro. Contrato"
    col_map = {
        "cliente": "nome_cliente",
        "nome": "nome_cliente",
        "sacado": "nome_cliente",
        "vencto": "data_vencimento",
        "vencimento": "data_vencimento",
        "dt_venc": "data_vencimento",
        "valor": "valor_parcela",
        "vlr_titulo": "valor_parcela",
        "contrato": "contrato",
        "nr_contrato": "contrato",
        "cpf": "cpf_cnpj",
        "cgc_cpf": "cpf_cnpj",
        "fone": "telefone",
        "telefone": "telefone"
    }
    
    # Rename columns based on map (partial match)
    new_cols = {}
    for c in df.columns:
        for k, v in col_map.items():
            if k in c and v not in new_cols.values():
                 new_cols[c] = v
                 break
    
    df = df.rename(columns=new_cols)
    
    # Verify required
    required = ["nome_cliente", "valor_parcela", "data_vencimento"]
    missing = [c for c in required if c not in df.columns]
    
    if missing:
        # Try to find again without mapping if simple names match?
        # Or just fail
        return {"error": f"Colunas não identificadas: {', '.join(missing)}. Colunas encontradas: {list(df.columns)}"}

    processed_customers = 0
    processed_installments = 0
    errors = []

    for index, row in df.iterrows():
        try:
            # 1. Customer
            name = str(row.get("nome_cliente", "Sem Nome")).strip()
            if pd.isna(name) or name == "nan": continue
            
            cpf = str(row.get("cpf_cnpj", "")).strip()
            if pd.isna(cpf) or cpf == "nan": cpf = None
            
            customer = None
            if cpf:
                customer = db.query(Customer).filter(Customer.cpf_cnpj == cpf).first()
            if not customer:
                customer = db.query(Customer).filter(Customer.name == name).first()
                
            if not customer:
                customer = Customer(
                    name=name,
                    cpf_cnpj=cpf,
                    phone=str(row.get("telefone", "")) if "telefone" in row and not pd.isna(row["telefone"]) else None,
                    external_key=f"IMP-HTML-{datetime.now().timestamp()}-{index}"
                )
                db.add(customer)
                db.flush()
                processed_customers += 1
            
            # 2. Installment
            due_date = parse_date_html(row.get("data_vencimento"))
            if not due_date: continue
            
            amount = parse_money_html(row.get("valor_parcela"))
            
            contract_id = str(row.get("contrato", f"CTR-{customer.id}-{index}")).strip()
            if pd.isna(contract_id) or contract_id == "nan": contract_id = f"CTR-{customer.id}-{index}"
            
            inst = db.query(Installment).filter(
                Installment.customer_id == customer.id,
                Installment.contract_id == contract_id,
                Installment.due_date == due_date
            ).first()
            
            if not inst:
                inst = Installment(
                    customer_id=customer.id,
                    contract_id=contract_id,
                    installment_number=1,
                    amount=amount,
                    open_amount=amount, # Assume full open
                    due_date=due_date,
                    status="ABERTA"
                )
                db.add(inst)
                processed_installments += 1
                
        except Exception as e:
            errors.append(f"Linha {index}: {str(e)}")

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        return {"error": f"Erro ao salvar no banco: {str(e)}"}

    return {
        "success": True,
        "customers": processed_customers,
        "installments": processed_installments,
        "errors": errors[:10]
    }
