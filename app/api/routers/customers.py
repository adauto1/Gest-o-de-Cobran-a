import logging
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload, subqueryload
from sqlalchemy import func
from decimal import Decimal
from datetime import datetime
from typing import Optional, List

from app.core.database import get_db
from app.models import Customer, Installment, CollectionAction, User, days_overdue
from app.core.web import render, require_login
from app.core.helpers import get_regua_nivel, bucket_priority, wa_link, stores_list, get_status_label, rule_for_overdue, format_money
from app.schemas import PriorityQueueResponse, PriorityQueueItem, CustomerUpdate

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/customers", response_class=HTMLResponse)
def customers_page(request: Request, q: str = "", store: str = "", db: Session = Depends(get_db)):
    user = require_login(request, db)
    query = db.query(Customer)
    if user.role == "COBRANCA" and user.store:
        query = query.filter(Customer.store == user.store)
    if store:
        query = query.filter(Customer.store == store)

    if q.strip():
        s = f"%{q.strip()}%"
        query = query.filter(Customer.name.ilike(s))

    query = query.options(
        subqueryload(Customer.installments),
        joinedload(Customer.assigned_to)
    )

    customers = query.order_by(Customer.name.asc()).limit(300).all()
    rows = []
    for c in customers:
        insts = [i for i in c.installments if i.status == "ABERTA" and Decimal(i.open_amount) > 0]
        if insts:
            max_over = max(days_overdue(i.due_date) for i in insts)
            total_open = sum(Decimal(i.open_amount) for i in insts)
            count_open = len(insts)
        else:
            max_over, total_open, count_open = 0, Decimal("0"), 0
        
        last = db.query(CollectionAction).filter(CollectionAction.customer_id == c.id).order_by(CollectionAction.created_at.desc()).first()
        ultimo_contato_str = last.created_at.strftime("%d/%m/%Y") if last else "Sem contato"
        regua_nivel = get_regua_nivel(c.profile_cobranca, max_over)
        
        if max_over > 60: status_label = get_status_label(max_over)
        elif max_over > 30: status_label = get_status_label(max_over)
        elif max_over > 0: status_label = get_status_label(max_over)
        else: status_label = "Em dia"

        rows.append({
            "c": c, 
            "max_over": max_over, 
            "total_open": total_open, 
            "count_open": count_open,
            "prio": bucket_priority(max_over), 
            "regua_nivel": regua_nivel,
            "ultimo_contato_str": ultimo_contato_str,
            "status_label": status_label
        })

    users = db.query(User).filter(User.active == True).order_by(User.name.asc()).all() if user.role == "ADMIN" else []
    return render("customers.html", request=request, user=user, title="Clientes",
                  rows=rows, q=q, store=store, stores=stores_list(db), users=users)

@router.get("/customers/{customer_id}", response_class=HTMLResponse)
def customer_detail_page(request: Request, customer_id: int, db: Session = Depends(get_db)):
    user = require_login(request, db)
    c = db.get(Customer, customer_id)
    if not c:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    if user.role == "COBRANCA":
        if user.store and (c.store or "").upper() != user.store.upper():
            raise HTTPException(status_code=403, detail="Sem acesso (loja)")
        assigned_exist = db.query(Customer).filter(Customer.assigned_to_user_id != None).count() > 0
        if assigned_exist and c.assigned_to_user_id != user.id:
            raise HTTPException(status_code=403, detail="Sem acesso (carteira)")

    open_insts = [i for i in c.installments if i.status == "ABERTA" and Decimal(i.open_amount) > 0]
    max_over = max([days_overdue(i.due_date) for i in open_insts], default=0)
    total_open = sum([Decimal(i.open_amount) for i in open_insts], Decimal("0"))

    from app.core.helpers import rule_for_overdue, format_money
    # Imports já no topo — mantido por compatibilidade com código legado
    
    effective_profile = get_regua_nivel(c.profile_cobranca, max_over)

    rule = rule_for_overdue(db, max_over, level=effective_profile)
    template = rule.template_message if rule else "Olá {nome}. Vamos regularizar? — Portal Móveis"
    
    next_due = min([i.due_date for i in open_insts], default=None)
    replacements = {
        "{nome}": c.name, "{NOME}": c.name,
        "{vencimento}": (next_due.strftime("%d/%m/%Y") if next_due else ""),
        "{valor}": (format_money(open_insts[0].open_amount) if open_insts else ""),
        "{total}": format_money(total_open),
        "{dias_atraso}": str(max_over),
    }
    
    msg = template
    for k, v in replacements.items():
        msg = msg.replace(k, v)
    link = wa_link(c.whatsapp, msg)

    actions = db.query(CollectionAction).filter(CollectionAction.customer_id == c.id).order_by(CollectionAction.created_at.desc()).limit(80).all()
    inst_view = []
    for i in sorted(c.installments, key=lambda inst: (inst.status != "ABERTA", inst.due_date)):
        od = days_overdue(i.due_date) if i.status == "ABERTA" and Decimal(i.open_amount) > 0 else 0
        inst_view.append({"i": i, "overdue": od})

    return render("customer.html", request=request, user=user, title="Cliente", customer=c,
                  installments=inst_view, actions=actions,
                  regua_nivel=get_regua_nivel(c.profile_cobranca, max_over),
                  total_open=format_money(total_open), max_overdue=max_over,
                  wa_link=link, wa_message=msg)

@router.post("/customers/{customer_id}/assign")
def assign_customer(request: Request, customer_id: int, assigned_to_user_id: int = Form(...), db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas ADMIN")
    c = db.get(Customer, customer_id)
    if not c:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    if assigned_to_user_id == 0:
        c.assigned_to_user_id = None
    else:
        u = db.get(User, assigned_to_user_id)
        if not u:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        c.assigned_to_user_id = u.id
    db.commit()
    return RedirectResponse("/customers", status_code=HTTP_302_FOUND)

@router.post("/customers/{customer_id}/change-profile")
def change_profile(request: Request, customer_id: int, profile: str = Form(...), db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role not in ["ADMIN", "COBRANCA"]:
        raise HTTPException(status_code=403, detail="Sem permissão")
    c = db.get(Customer, customer_id)
    if not c:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    if profile not in ["AUTOMATICO", "LEVE", "MODERADA", "INTENSA"]:
        raise HTTPException(status_code=400, detail="Perfil inválido")
    c.profile_cobranca = profile
    db.commit()
    referer = request.headers.get("referer")
    return RedirectResponse(referer or f"/customers/{customer_id}", status_code=HTTP_302_FOUND)

@router.patch("/api/customers/{customer_id}")
def update_customer_api(customer_id: int, dados: CustomerUpdate, request: Request, db: Session = Depends(get_db)):
    """Atualiza dados do cliente via AJAX. Usa schema CustomerUpdate para validação."""
    user = require_login(request, db)
    cliente = db.get(Customer, customer_id)
    if not cliente:
        return {"success": False, "message": "Cliente não encontrado"}
    if user.role == "COBRANCA" and user.store and (cliente.store or "").upper() != user.store.upper():
        return {"success": False, "message": "Sem permissão (loja)"}
    if dados.whatsapp is not None:
        cliente.whatsapp = dados.whatsapp.strip()
    if dados.address is not None:
        cliente.address = dados.address.strip()
    if dados.notes is not None:
        cliente.notes = dados.notes.strip()
    if dados.profile_cobranca is not None:
        cliente.profile_cobranca = dados.profile_cobranca
    if dados.email is not None:
        cliente.email = dados.email.strip()
    cliente.updated_at = datetime.utcnow()
    db.commit()
    return {"success": True, "message": "Cliente atualizado com sucesso"}
