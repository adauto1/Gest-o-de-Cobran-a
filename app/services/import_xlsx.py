import pandas as pd
from sqlalchemy.orm import Session
from datetime import datetime, date
import logging
from ..main import Customer, Installment, User, CollectionAction

# Validate Date Format
def parse_date_excel(val):
    if pd.isna(val):
        return None
    if isinstance(val, (datetime, date)):
        return val
    try:
        return pd.to_datetime(val, dayfirst=True).date()
    except:
        return None

def process_excel_import(file_content: bytes, db: Session, user_id: int):
    """
    Reads an Excel file and updates/creates Customers and Installments.
    Expected Columns:
    - Nome Cliente
    - CPF/CNPJ
    - Telefone
    - Email
    - Valor Parcela
    - Data Vencimento
    - Dias Atraso
    - Status
    - Ultimo Contato
    - Observacao
    - Loja (Optional)
    - Contrato (Optional)
    """
    try:
        df = pd.read_excel(file_content)
    except Exception as e:
        return {"error": f"Erro ao ler arquivo Excel: {str(e)}"}

    # Normalize columns
    df.columns = [c.strip().lower().replace(" ", "_").replace("/", "_") for c in df.columns]
    
    # Check Required Columns
    required = ["nome_cliente", "valor_parcela", "data_vencimento"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        return {"error": f"Colunas obrigatórias faltando: {', '.join(missing)}"}

    processed_customers = 0
    processed_installments = 0
    errors = []

    for index, row in df.iterrows():
        try:
            # 1. Customer
            name = str(row.get("nome_cliente", "Sem Nome")).strip()
            cpf = str(row.get("cpf_cnpj", "")).strip() if not pd.isna(row.get("cpf_cnpj")) else None
            
            # Simple deduplication by Name if CPF missing (or use external_key if available)
            # ideally we use CPF, but let's try to find by Name for simplicity in this MVP
            
            customer = None
            if cpf:
                 customer = db.query(Customer).filter(Customer.cpf_cnpj == cpf).first()
            
            if not customer:
                 customer = db.query(Customer).filter(Customer.name == name).first()

            if not customer:
                customer = Customer(
                    name=name,
                    cpf_cnpj=cpf,
                    phone=str(row.get("telefone", "")) if not pd.isna(row.get("telefone")) else None,
                    email=str(row.get("email", "")) if not pd.isna(row.get("email")) else None,
                    store=str(row.get("loja", "")) if not pd.isna(row.get("loja")) else None,
                    external_key=f"EXT-{datetime.now().timestamp()}-{index}" # Fallback
                )
                db.add(customer)
                db.flush() # Get ID
                processed_customers += 1
            else:
                # Update info
                if not pd.isna(row.get("telefone")):
                    customer.phone = str(row.get("telefone", ""))
                if not pd.isna(row.get("loja")):
                    customer.store = str(row.get("loja", ""))

            # 2. Installment
            due_date = parse_date_excel(row.get("data_vencimento"))
            if not due_date:
                continue

            amount = float(row.get("valor_parcela", 0))
            
            # Check if installment exists (dedup logic could be better, typically contract_id + installment_num)
            contract_id = str(row.get("contrato", f"CTR-{customer.id}-{index}"))
            
            inst = db.query(Installment).filter(
                Installment.customer_id == customer.id,
                Installment.contract_id == contract_id,
                Installment.due_date == due_date
            ).first()

            if not inst:
                inst = Installment(
                    customer_id=customer.id,
                    contract_id=contract_id,
                    installment_number=1, # Default
                    amount=amount,
                    open_amount=amount, # Assume full open if new import
                    due_date=due_date,
                    status="ABERTA"
                )
                db.add(inst)
                processed_installments += 1

        except Exception as e:
            errors.append(f"Linha {index+2}: {str(e)}")

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        return {"error": f"Erro de banco de dados: {str(e)}"}

    return {
        "success": True,
        "customers": processed_customers,
        "installments": processed_installments,
        "errors": errors[:10] # Limit header
    }
