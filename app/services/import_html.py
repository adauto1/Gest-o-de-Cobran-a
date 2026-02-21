
import pandas as pd
from sqlalchemy.orm import Session
from datetime import datetime
import re
import json
from bs4 import BeautifulSoup
from ..models import Customer, Installment, ReconciliationStats

def parse_date_str(s):
    try:
        return datetime.strptime(s.strip(), "%d/%m/%Y").date()
    except:
        return None

def parse_valor_br(texto):
    try:
        v = texto.strip().replace('.', '').replace(',', '.')
        return float(v)
    except:
        return 0.0

def detect_report_type(content: bytes):
    """
    Detecta se o relatório é de Títulos a Receber ou Títulos Recebidos.
    """
    text = content.decode('utf-8', errors='ignore').upper()
    if "RELATORIO DE TITULOS A RECEBER" in text:
        return "ABERTO"
    elif "RELATORIO DE TITULOS RECEBIDOS" in text:
        return "RECEBIDO"
    return "DESCONHECIDO"

def process_html_import(file_content: bytes, db: Session, user_id: int):
    """
    Integrador de HTML: Importa novos títulos ou realiza conferência de baixas.
    """
    report_type = detect_report_type(file_content)
    
    # Parsing comum (Reconstrução por coordenadas)
    try:
        soup = BeautifulSoup(file_content, "html.parser")
    except Exception as e:
        return {"error": f"Erro HTML Soup: {e}"}

    elements = []
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
        return {"error": "Dados não encontrados no HTML."}

    elements.sort(key=lambda x: (x['top'], x['left']))
    rows = []
    current_row = [elements[0]]
    current_y = elements[0]['top']
    for el in elements[1:]:
        if abs(el['top'] - current_y) <= 4:
            current_row.append(el)
        else:
            rows.append(current_row)
            current_row = [el]
            current_y = el['top']
    rows.append(current_row)

    if report_type == "RECEBIDO":
        return _handle_reconciliation(rows, db)
    else:
        # Lógica original de importação (Aberto/Vencido)
        return _handle_standard_import(rows, db, user_id)

def _handle_standard_import(rows, db: Session, user_id: int):
    processed_customers = 0
    processed_installments = 0
    errors = []
    re_date = re.compile(r'\d{2}/\d{2}/\d{4}')
    re_money = re.compile(r'\d{1,3}(?:\.\d{3})*,\d{2}')

    for i, row in enumerate(rows):
        row.sort(key=lambda x: x['left'])
        candidates_date = []
        candidates_amount = []
        for el in row:
            if re_date.match(el['text']): candidates_date.append(el)
            elif re_money.match(el['text']): candidates_amount.append(el)
        
        valid_date = next((c for c in candidates_date if 550 <= c['left'] <= 630), None)
        valid_amount = next((c for c in candidates_amount if 630 <= c['left'] <= 700), None)
        
        if valid_date and valid_amount:
            due_date = parse_date_str(valid_date['text'])
            amount = parse_valor_br(valid_amount['text'])
            name_parts = []
            contract_txt = ""
            for el in row:
                if el == valid_date or el == valid_amount: continue
                if el['left'] < 500:
                    if el['left'] > 450 and len(el['text']) < 15: contract_txt = el['text']
                    else: name_parts.append(el['text'])
            name = " ".join(name_parts).strip()
            if re.match(r'^\d{2}/\d{2}/', name) or not name or len(name) < 3: continue
            if not contract_txt: contract_txt = f"CTR-{i}"

            try:
                customer = db.query(Customer).filter(Customer.name == name).first()
                if not customer:
                    customer = Customer(name=name, external_key=f"IMP-{datetime.now().timestamp()}-{i}")
                    db.add(customer); db.flush()
                    processed_customers += 1
                
                inst = db.query(Installment).filter(
                    Installment.customer_id == customer.id,
                    Installment.contract_id == contract_txt,
                    Installment.due_date == due_date
                ).first()
                if not inst:
                    db.add(Installment(
                        customer_id=customer.id, contract_id=contract_txt,
                        amount=amount, open_amount=amount, due_date=due_date, status="ABERTA"
                    ))
                    processed_installments += 1
            except Exception as e:
                errors.append(str(e))
    db.commit()
    return {"success": True, "customers": processed_customers, "installments": processed_installments, "report_type": "ABERTO"}

def _handle_reconciliation(rows, db: Session):
    total_paid = 0
    normally_paid = 0
    cancelled_list = []
    re_date = re.compile(r'\d{2}/\d{2}/\d{4}')
    
    # RDPrint 5.0 positions for Recebidos: 522=Doc, 588=Vencimento, 762=Status(QUITADA)
    for row in rows:
        row.sort(key=lambda x: x['left'])
        # Check if it's a data row (starts with date at left:54)
        start_el = next((el for el in row if el['left'] == 54), None)
        if not start_el or not re_date.match(start_el['text']): continue
        
        doc = next((el['text'] for el in row if el['left'] == 522), None)
        venc = next((el['text'] for el in row if el['left'] == 588), None)
        status = next((el['text'] for el in row if el['left'] == 762), None)
        
        if doc and venc and status == "QUITADA":
            total_paid += 1
            due_date = parse_date_str(venc)
            # Check in App DB
            inst = db.query(Installment).filter(
                Installment.contract_id == doc,
                Installment.due_date == due_date
            ).first()
            
            if inst:
                normally_paid += 1
                # Se ainda estiver aberta no app, poderíamos quitar, 
                # mas o requisito foca na estatística e no dashboard.
            else:
                name = next((el['text'] for el in row if el['left'] == 264), "Desconhecido")
                cancelled_list.append({"doc": doc, "venc": venc, "cliente": name})

    # Persistir estatísticas
    try:
        stats = db.query(ReconciliationStats).filter(ReconciliationStats.date == datetime.utcnow().date()).first()
        if not stats:
            stats = ReconciliationStats(date=datetime.utcnow().date())
            db.add(stats)
        
        stats.total_paid_erp = total_paid
        stats.normally_paid = normally_paid
        stats.cancelled_or_deleted = len(cancelled_list)
        stats.details_json = json.dumps(cancelled_list)
        db.commit()
    except Exception as e:
        db.rollback()
        return {"error": f"Erro ao salvar estatísticas: {e}"}

    return {
        "success": True,
        "report_type": "RECEBIDO",
        "total": total_paid,
        "normal": normally_paid,
        "cancelled": len(cancelled_list),
        "details": cancelled_list[:10] # Amostra
    }
