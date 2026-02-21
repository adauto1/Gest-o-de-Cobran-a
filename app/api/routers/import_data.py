from fastapi import APIRouter, Request, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from decimal import Decimal
from datetime import datetime
import csv
import io
import re
from typing import Optional, List, Dict
from bs4 import BeautifulSoup

from app.core.database import get_db
from app.models import (
    Customer, Installment, CollectionAction, SentMessage, 
    ComissaoCobranca, User
)
from app.core.web import render, require_login
import os
from app.core.helpers import parse_decimal, parse_date_br as parse_date
from app.services.sync_customers import sync_erp_customers

router = APIRouter()

@router.post("/api/sync/customers")
def sync_customers_api(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas ADMIN")
    
    # Busca o arquivo HTM na pasta de dados padrão
    data_dir = os.getenv("DATA_DIR", "data")
    erp_file = os.path.join(data_dir, "RELATORIO.HTM")
    
    if not os.path.exists(erp_file):
        # Tenta buscar qualquer .HTM se o padrão não existir
        if os.path.exists(data_dir):
            for f in os.listdir(data_dir):
                if f.upper().endswith(".HTM"):
                    erp_file = os.path.join(data_dir, f)
                    break

    if not os.path.exists(erp_file):
         return {"success": False, "detail": f"Arquivo ERP não encontrado em {data_dir}"}

    result = sync_erp_customers(erp_file, db)
    return result

def read_csv_upload(file: UploadFile) -> List[Dict[str, str]]:
    content = file.file.read()
    try:
        text = content.decode("utf-8-sig")
    except Exception:
        text = content.decode("latin-1")
    f = io.StringIO(text)
    return [dict(r) for r in csv.DictReader(f)]

def parse_valor_br(texto):
    try:
        v = texto.strip().replace('.', '').replace(',', '.')
        return float(v)
    except:
        return 0.0

def parse_infocommerce_html(content: bytes) -> List[Dict]:
    """Parse HTML do InfoCommerce extraindo títulos por posicionamento CSS."""
    try:
        text = content.decode('latin-1', errors='ignore')
    except:
        text = content.decode('utf-8', errors='ignore')
    
    soup = BeautifulSoup(text, 'lxml')
    tags = soup.find_all(['div', 'p', 'span'])
    
    rows_data = {}
    for tag in tags:
        style = tag.get('style', '')
        top_match = re.search(r'top:(\d+)px', style)
        left_match = re.search(r'left:(\d+)px', style)
        txt = tag.get_text().strip()
        
        if top_match and left_match and txt:
            top = int(top_match.group(1))
            left = int(left_match.group(1))
            if top not in rows_data:
                rows_data[top] = {}
            rows_data[top][left] = txt
    
    parsed = []
    for top in sorted(rows_data.keys()):
        row = rows_data[top]
        emissao = row.get(54)
        vencimento = row.get(588)
        pedido = row.get(132)
        cliente = row.get(264)
        valor_raw = row.get(648)

        if emissao and vencimento:
            if re.match(r'\d{2}/\d{2}/\d{4}', emissao) and re.match(r'\d{2}/\d{2}/\d{4}', vencimento):
                if valor_raw:
                    valor = parse_valor_br(valor_raw)
                    if valor > 0:
                        parsed.append({
                            'vencimento': vencimento,
                            'cliente': (cliente or "DESCONHECIDO").strip().upper(),
                            'valor': valor,
                            'pedido': (pedido or "").strip()
                        })
    return parsed

@router.get("/import", response_class=HTMLResponse)
def import_page(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas ADMIN")
    return render("import.html", request=request, user=user, title="Importação")

@router.post("/import/customers")
def import_customers(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas ADMIN")

    rows = read_csv_upload(file)
    errors = 0
    upserts = 0
    for r in rows:
        ext = (r.get("cliente_id") or "").strip()
        name = (r.get("nome") or "").strip()
        if not ext or not name:
            errors += 1
            continue
        cust = db.query(Customer).filter(Customer.external_key == ext).first()
        if not cust:
            cust = Customer(external_key=ext, name=name)
            db.add(cust)
        cust.name = name
        cust.cpf_cnpj = (r.get("cpf_cnpj") or "").strip() or None
        cust.whatsapp = (r.get("telefone_whatsapp") or "").strip() or None
        cust.store = (r.get("loja") or "").strip() or None
        cust.address = (r.get("endereco") or "").strip() or None
        upserts += 1
    db.commit()
    return RedirectResponse(f"/import?msg=Clientes importados: {upserts}. Erros: {errors}.", status_code=302)

@router.post("/import/installments")
def import_installments(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas ADMIN")

    rows = read_csv_upload(file)
    errors = 0
    upserts = 0
    for r in rows:
        ext = (r.get("cliente_id") or "").strip()
        cust = db.query(Customer).filter(Customer.external_key == ext).first()
        if not cust:
            errors += 1
            continue
        try:
            contract_id = (r.get("contrato_id") or "").strip()
            inst_no = int((r.get("parcela_numero") or "1").strip())
            due = parse_date(r.get("vencimento") or "")
            amount = parse_decimal(r.get("valor_parcela") or "0")
            open_amount = parse_decimal(r.get("valor_em_aberto") or "0")
            status = (r.get("status") or "ABERTA").strip().upper()
        except Exception:
            errors += 1
            continue

        inst = db.query(Installment).filter(
            Installment.customer_id == cust.id,
            Installment.contract_id == contract_id,
            Installment.installment_number == inst_no,
            Installment.due_date == due
        ).first()
        if not inst:
            inst = Installment(
                customer_id=cust.id,
                contract_id=contract_id,
                installment_number=inst_no,
                due_date=due,
                amount=amount,
                open_amount=open_amount,
                status=status
            )
            db.add(inst)
        else:
            inst.amount = amount
            inst.open_amount = open_amount
            inst.status = status
        upserts += 1
    db.commit()
    return RedirectResponse(f"/import?msg=Parcelas importadas: {upserts}. Erros: {errors}.", status_code=302)

@router.post("/import/upload")
def import_erp_upload(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Importa dados do ERP a partir de arquivo HTML (InfoCommerce) ou Excel."""
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas ADMIN")
    
    content = file.file.read()
    filename = file.filename.lower()
    
    if filename.endswith(('.html', '.htm')):
        parsed_data = parse_infocommerce_html(content)
        if not parsed_data:
            return RedirectResponse("/import?msg=Erro: Nenhum dado encontrado no arquivo HTML.", status_code=302)
        
        open_installments = db.query(Installment).filter(Installment.status == "ABERTA").all()
        existing_keys = {(inst.customer_id, inst.due_date, inst.amount) for inst in open_installments}
        
        customers_cache = {}
        count_customers = 0
        count_installments = 0
        errors = 0
        new_keys = set()
        
        for item in parsed_data:
            try:
                cliente_name = item['cliente']
                if cliente_name not in customers_cache:
                    cust = db.query(Customer).filter(Customer.external_key == cliente_name).first()
                    if not cust:
                        cust = Customer(external_key=cliente_name, name=cliente_name, whatsapp="", store="LOJA 1")
                        db.add(cust)
                        db.flush()
                        count_customers += 1
                    customers_cache[cliente_name] = cust.id
                
                due_date = datetime.strptime(item['vencimento'], '%d/%m/%Y').date()
                valor = Decimal(str(item['valor']))
                new_keys.add((customers_cache[cliente_name], due_date, valor))
                
                inst = db.query(Installment).filter(
                    Installment.customer_id == customers_cache[cliente_name],
                    Installment.due_date == due_date,
                    Installment.amount == valor
                ).first()
                
                if not inst:
                    pedido_id = item.get('pedido') or f"ERP-{cliente_name[:10]}-{due_date.strftime('%Y%m%d')}"
                    inst = Installment(
                        customer_id=customers_cache[cliente_name],
                        contract_id=pedido_id,
                        installment_number=1,
                        due_date=due_date,
                        amount=valor,
                        open_amount=valor,
                        status="ABERTA"
                    )
                    db.add(inst)
                    count_installments += 1
                else:
                    inst.open_amount = valor
                    inst.status = "ABERTA"
                    count_installments += 1
            except Exception:
                errors += 1
                continue
        
        paid_keys = existing_keys - new_keys
        count_paid = 0
        for customer_id, due_date, amount in paid_keys:
            inst = db.query(Installment).filter(
                Installment.customer_id == customer_id,
                Installment.due_date == due_date,
                Installment.amount == amount,
                Installment.status == "ABERTA"
            ).first()
            if inst:
                inst.status = "PAGA"
                inst.paid_at = datetime.now()
                inst.open_amount = Decimal("0")
                count_paid += 1
        
        db.commit()
        msg = f"Importação concluída! Clientes: {count_customers} novos. Parcelas: {count_installments}. Baixadas: {count_paid}. Erros: {errors}."
        return RedirectResponse(f"/import?msg={msg}", status_code=302)
    elif filename.endswith(('.xlsx', '.xls')):
        return RedirectResponse("/import?msg=Erro: Excel ainda não implementado.", status_code=302)
    return RedirectResponse("/import?msg=Erro: Formato não suportado.", status_code=302)

@router.post("/import/reset")
def reset_database(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas ADMIN")
    
    try:
        db.query(CollectionAction).delete()
        db.query(SentMessage).delete()
        db.query(ComissaoCobranca).delete()
        deleted_installments = db.query(Installment).delete()
        deleted_customers = db.query(Customer).delete()
        db.commit()
        msg = f"App zerado! Removidos: {deleted_customers} clientes e {deleted_installments} parcelas."
        return RedirectResponse(f"/import?msg={msg}", status_code=302)
    except Exception as e:
        db.rollback()
        return RedirectResponse(f"/import?msg=Erro ao zerar: {str(e)}", status_code=302)
