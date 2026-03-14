import logging
import csv
import io
from pydantic import BaseModel
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session, joinedload, subqueryload
from starlette.status import HTTP_302_FOUND
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Optional

from app.core.database import get_db
from app.models import Customer, Installment, CollectionAction, User, days_overdue
from app.core.web import render, require_login
from app.core.helpers import get_regua_nivel, bucket_priority, wa_link, stores_list, get_status_label, rule_for_overdue, format_money, get_last_contacts_map
from app.schemas import CustomerUpdate

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/customers", response_class=HTMLResponse)
def customers_page(request: Request, q: str = "", store: str = "", filtro: str = "", db: Session = Depends(get_db)):
    user = require_login(request, db)
    query = db.query(Customer)
    if user.role == "COBRANCA" and user.store:
        query = query.filter(Customer.store == user.store)
    if store:
        query = query.filter(Customer.store == store)
    if q.strip():
        query = query.filter(Customer.name.ilike(f"%{q.strip()}%"))

    # Filtros do funil de cobrança
    if filtro == "contatados":
        periodo = datetime.utcnow() - timedelta(days=30)
        ids = db.query(CollectionAction.customer_id).filter(
            CollectionAction.created_at >= periodo
        ).distinct()
        query = query.filter(Customer.id.in_(ids))
    elif filtro == "pagos":
        periodo = datetime.utcnow() - timedelta(days=30)
        ids = db.query(Installment.customer_id).filter(
            Installment.status == "PAGA",
            Installment.paid_at >= periodo
        ).distinct()
        query = query.filter(Customer.id.in_(ids))

    query = query.options(
        subqueryload(Customer.installments),
        joinedload(Customer.assigned_to)
    )

    customers = query.order_by(Customer.name.asc()).limit(300).all()
    last_contacts = get_last_contacts_map(db, [c.id for c in customers])
    rows = []
    for c in customers:
        insts = [i for i in c.installments if i.status == "ABERTA" and Decimal(i.open_amount) > 0]
        if not insts and not q.strip() and not filtro:
            continue
        if insts:
            max_over = max(days_overdue(i.due_date) for i in insts)
            total_open = sum(Decimal(i.open_amount) for i in insts)
            count_open = len(insts)
        else:
            max_over, total_open, count_open = 0, Decimal("0"), 0

        rows.append({
            "c": c,
            "max_over": max_over,
            "total_open": total_open,
            "count_open": count_open,
            "prio": bucket_priority(max_over),
            "regua_nivel": get_regua_nivel(c.profile_cobranca, max_over),
            "ultimo_contato_str": last_contacts.get(c.id, "Sem contato"),
            "status_label": get_status_label(max_over),
        })

    users = db.query(User).filter(User.active == True).order_by(User.name.asc()).all() if user.role == "ADMIN" else []
    return render("customers.html", request=request, user=user, title="Clientes",
                  rows=rows, q=q, store=store, filtro=filtro, stores=stores_list(db), users=users)

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

    _today = datetime.now().date()
    _yesterday = _today - timedelta(days=1)
    return render("customer.html", request=request, user=user, title="Cliente", customer=c,
                  installments=inst_view, actions=actions,
                  regua_nivel=get_regua_nivel(c.profile_cobranca, max_over),
                  total_open=format_money(total_open), max_overdue=max_over,
                  wa_link=link, wa_message=msg,
                  today=_today.strftime("%d/%m/%Y"),
                  yesterday=_yesterday.strftime("%d/%m/%Y"))

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

@router.post("/customers/{customer_id}/toggle-msgs")
def toggle_msgs(request: Request, customer_id: int, db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role not in ["ADMIN", "COBRANCA"]:
        raise HTTPException(status_code=403, detail="Sem permissao")
    c = db.get(Customer, customer_id)
    if not c:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")
    c.msgs_ativo = not getattr(c, 'msgs_ativo', True)
    db.commit()
    return {"success": True, "msgs_ativo": c.msgs_ativo}

class PausarBody(BaseModel):
    pausado_ate: Optional[str] = None  # 'YYYY-MM-DD' ou null para remover pausa

@router.patch("/api/customers/{customer_id}/pausar")
def pausar_cobranca(customer_id: int, body: PausarBody, request: Request, db: Session = Depends(get_db)):
    """Define ou remove pausa de cobrança automática. pausado_ate=null remove a pausa."""
    from datetime import date as date_type
    user = require_login(request, db)
    if user.role not in ["ADMIN", "COBRANCA"]:
        raise HTTPException(status_code=403, detail="Sem permissão")
    c = db.get(Customer, customer_id)
    if not c:
        return {"success": False, "message": "Cliente não encontrado"}
    if body.pausado_ate:
        try:
            c.pausado_ate = date_type.fromisoformat(body.pausado_ate)
        except ValueError:
            return {"success": False, "message": "Data inválida"}
    else:
        c.pausado_ate = None
    db.commit()
    return {"success": True, "pausado_ate": c.pausado_ate.isoformat() if c.pausado_ate else None}

@router.get("/api/customers/{customer_id}")
def get_customer_api(customer_id: int, request: Request, db: Session = Depends(get_db)):
    """Retorna dados do cliente para preencher o modal de edição."""
    require_login(request, db)
    c = db.get(Customer, customer_id)
    if not c:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return {
        "id": c.id,
        "name": c.name,
        "whatsapp": c.whatsapp or "",
        "address": c.address or "",
        "email": c.email or "",
        "notes": c.notes or "",
        "profile_cobranca": c.profile_cobranca or "AUTOMATICO",
        "perfil_devedor": getattr(c, "perfil_devedor", None) or "NORMAL",
    }

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
    if dados.perfil_devedor is not None:
        if dados.perfil_devedor in ("NORMAL", "BOM_PAGADOR", "RECORRENTE", "DIFICIL"):
            cliente.perfil_devedor = dados.perfil_devedor
    cliente.updated_at = datetime.utcnow()
    db.commit()
    return {"success": True, "message": "Cliente atualizado com sucesso"}


@router.get("/export/clientes.csv")
def export_clientes_csv(
    request: Request,
    store: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Exporta clientes com parcelas abertas para CSV."""
    require_login(request, db)

    query = db.query(Customer).options(subqueryload(Customer.installments))
    if store:
        query = query.filter(Customer.store == store)
    customers = query.order_by(Customer.name).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Nome", "WhatsApp", "Loja", "Parcelas Abertas", "Total Aberto (R$)", "Maior Atraso (dias)", "Perfil Devedor"])

    for c in customers:
        insts = [i for i in c.installments if i.status == "ABERTA" and Decimal(i.open_amount) > 0]
        if not insts:
            continue
        max_over = max(days_overdue(i.due_date) for i in insts)
        total_open = sum(Decimal(i.open_amount) for i in insts)
        writer.writerow([
            c.name,
            c.whatsapp or "",
            c.store or "",
            len(insts),
            f"{total_open:.2f}".replace(".", ","),
            max_over,
            getattr(c, "perfil_devedor", "NORMAL") or "NORMAL",
        ])

    output.seek(0)
    headers = {"Content-Disposition": "attachment; filename=clientes.csv"}
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv; charset=utf-8", headers=headers)


@router.get("/export/promessas.csv")
def export_promessas_csv(
    request: Request,
    mes: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Exporta promessas do mês para CSV. mes=YYYY-MM, padrão = mês atual."""
    require_login(request, db)

    from app.models import CollectionAction, User as UserModel
    hoje = datetime.utcnow()
    if mes:
        try:
            ano, m = int(mes.split("-")[0]), int(mes.split("-")[1])
        except Exception:
            ano, m = hoje.year, hoje.month
    else:
        ano, m = hoje.year, hoje.month

    inicio = datetime(ano, m, 1)
    if m == 12:
        fim = datetime(ano + 1, 1, 1)
    else:
        fim = datetime(ano, m + 1, 1)

    rows = db.query(CollectionAction, Customer, UserModel).join(
        Customer, Customer.id == CollectionAction.customer_id
    ).join(
        UserModel, UserModel.id == CollectionAction.user_id
    ).filter(
        CollectionAction.outcome.in_(["PROMESSA", "PROMESSA_PAGAMENTO"]),
        CollectionAction.created_at >= inicio,
        CollectionAction.created_at < fim,
    ).order_by(CollectionAction.promised_date).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Data Promessa", "Cliente", "Valor Prometido (R$)", "Cobrador", "Registrado Em"])

    for action, cust, usr in rows:
        writer.writerow([
            action.promised_date.strftime("%d/%m/%Y") if action.promised_date else "",
            cust.name,
            f"{action.promised_amount:.2f}".replace(".", ",") if action.promised_amount else "",
            usr.name,
            action.created_at.strftime("%d/%m/%Y %H:%M"),
        ])

    output.seek(0)
    headers = {"Content-Disposition": f"attachment; filename=promessas-{ano}-{m:02d}.csv"}
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv; charset=utf-8", headers=headers)
