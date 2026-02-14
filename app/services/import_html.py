
import pandas as pd
from sqlalchemy.orm import Session
from datetime import datetime
import re
from bs4 import BeautifulSoup
from ..main import Customer, Installment

def parse_date_str(s):
    try:
        return datetime.strptime(s.strip(), "%d/%m/%Y").date()
    except:
        return None

def parse_money_str(s):
    try:
        clean = s.replace(".", "").replace(",", ".").strip()
        return float(clean)
    except:
        return None

def process_html_import(file_content: bytes, db: Session, user_id: int):
    """
    Parses HTML report (InfoCommerce div-based) by reconstructing rows from coordinates.
    """
    try:
        # Check if it's a standard table first (fallback)
        dfs = pd.read_html(file_content, header=0, decimal=",", thousands=".")
        if len(dfs) > 0 and len(dfs[0].columns) > 3:
             # Logic for table-based HTML (if any found)
             pass 
    except:
        pass

    # Div-based parsing
    try:
        soup = BeautifulSoup(file_content, "html.parser")
    except Exception as e:
        return {"error": f"Erro HTML Soup: {e}"}

    elements = []
    # Regex to extract top/left
    # style="... top:123;left:456; ..."
    re_top = re.compile(r'top:(\d+)')
    re_left = re.compile(r'left:(\d+)')

    for div in soup.find_all("div"):
        style = div.get("style", "")
        if not style: continue
        
        tm = re_top.search(style)
        lm = re_left.search(style)
        if tm and lm:
            text = div.get_text(" ", strip=True)
            if not text: continue
            elements.append({
                'top': int(tm.group(1)),
                'left': int(lm.group(1)),
                'text': text
            })

    if not elements:
         return {"error": "Não foi possível ler os dados do HTML (nenhum elemento posicionado encontrado)."}

    # Sort by Y then X
    elements.sort(key=lambda x: (x['top'], x['left']))

    # Group into rows
    rows = []
    current_row = [elements[0]]
    current_y = elements[0]['top']

    for el in elements[1:]:
        if abs(el['top'] - current_y) <= 4: # Tolerance 4px
            current_row.append(el)
        else:
            rows.append(current_row)
            current_row = [el]
            current_y = el['top']
    rows.append(current_row)

    processed_customers = 0
    processed_installments = 0
    errors = []
    
    # Regex patterns
    re_date = re.compile(r'\d{2}/\d{2}/\d{4}')
    re_money = re.compile(r'\d{1,3}(?:\.\d{3})*,\d{2}')

    for i, row in enumerate(rows):
        # Sort row by X
        row.sort(key=lambda x: x['left'])
        
        # Identify columns by content pattern
        date_el = None
        amount_el = None
        name_el = None
        contract_el = None
        
        # Heuristic:
        # Date is usually dd/mm/yyyy
        # Amount matches money regex
        # Name is usually the FIRST element (leftmost) if not date/amount
        
        # We need to find the "Due Date" specifically (Vencimento)
        # Sometimes there are multiple dates (Reference date etc).
        # Based on debug: Due Date x=588, Amount x=648.
        
        candidates_date = []
        candidates_amount = []
        
        for el in row:
            txt = el['text']
            if re_date.match(txt):
                candidates_date.append(el)
            elif re_money.match(txt):
                candidates_amount.append(el)
                
        # Filter by X position (approximate) based on our debug
        # Date ~ 588
        valid_date = None
        for cand in candidates_date:
            if 550 <= cand['left'] <= 630:
                valid_date = cand
                break
        
        # Amount ~ 648
        valid_amount = None
        for cand in candidates_amount:
            if 630 <= cand['left'] <= 700:
                valid_amount = cand
                break
                
        if valid_date and valid_amount:
            # Likely a data row
            due_date = parse_date_str(valid_date['text'])
            amount = parse_money_str(valid_amount['text'])
            
            # Name: Leftmost element < 400
            # Contract: Element between Name and Date? Or specific X (~522)
            
            name_parts = []
            contract_txt = ""
            
            for el in row:
                if el == valid_date or el == valid_amount: continue
                
                # Name range
                if el['left'] < 500:
                    # Check if it looks like contract (digits only or short?)
                    if el['left'] > 450 and len(el['text']) < 15:
                         contract_txt = el['text']
                    else:
                         name_parts.append(el['text'])
                
            name = " ".join(name_parts).strip()
            
            # Validation
            if not name or len(name) < 3: continue 
            # sometimes header row has "Vencimento" which matches nothing, good.
            # But if header has "01/01/2023" as example? Unlikely.
            
            if not contract_txt:
                 contract_txt = f"CTR-{i}"

            try:
                # DB Operations
                customer = None
                # Try find by Name
                customer = db.query(Customer).filter(Customer.name == name).first()
                
                if not customer:
                    customer = Customer(
                        name=name,
                        cpf_cnpj=None,
                        external_key=f"IMP-DIV-{datetime.now().timestamp()}-{i}"
                    )
                    db.add(customer)
                    db.flush()
                    processed_customers += 1
                
                # Check Installment
                inst = db.query(Installment).filter(
                    Installment.customer_id == customer.id,
                    Installment.contract_id == contract_txt,
                    Installment.due_date == due_date
                ).first()
                
                if not inst:
                    inst = Installment(
                        customer_id=customer.id,
                        contract_id=contract_txt,
                        installment_number=1,
                        amount=amount,
                        open_amount=amount,
                        due_date=due_date,
                        status="ABERTA"
                    )
                    db.add(inst)
                    processed_installments += 1
                    
            except Exception as e:
                errors.append(f"Row {i}: {e}")

    try:
        db.commit()
    except:
        db.rollback()
        return {"error": "Erro ao salvar dados."}

    return {
        "success": True, 
        "customers": processed_customers, 
        "installments": processed_installments,
        "errors": errors[:5]
    }
