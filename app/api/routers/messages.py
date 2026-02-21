from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from typing import Optional, List
from datetime import datetime
from starlette.status import HTTP_302_FOUND

from app.core.database import get_db, SessionLocal
from app.models import (
    SentMessage, MessageDispatchLog, WhatsappHistorico, 
    FinancialAlertLog, FinancialUser, today
)
from app.core.web import render, require_login

router = APIRouter()

@router.get("/outbox", response_class=HTMLResponse)
def outbox_page(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    return render("outbox.html", request=request, user=user, title="Fila de Envio")

@router.get("/api/mensagens/outbox")
def get_outbox_api(
    request: Request,
    page: int = 1,
    limit: int = 50,
    date_from: str = None,
    date_to: str = None,
    status: str = None,
    regua: str = None,
    cliente: str = None,
    only_test: bool = False,
    db: Session = Depends(get_db)
):
    require_login(request, db)
    query = db.query(MessageDispatchLog)

    if date_from:
        df = datetime.strptime(date_from, "%Y-%m-%d").date()
        query = query.filter(MessageDispatchLog.scheduled_for >= df)
    if date_to:
        dt = datetime.strptime(date_to, "%Y-%m-%d").date()
        query = query.filter(MessageDispatchLog.scheduled_for <= dt)
    if status:
        query = query.filter(MessageDispatchLog.status == status)
    if regua:
        query = query.filter(MessageDispatchLog.regua == regua)
    if cliente:
        s = f"%{cliente}%"
        query = query.filter(
            (MessageDispatchLog.customer_name.ilike(s)) |
            (MessageDispatchLog.destination_phone.ilike(s)) |
            (MessageDispatchLog.cpf_mask.ilike(s))
        )
    if only_test:
        query = query.filter(MessageDispatchLog.mode == "TEST")

    # KPIs (Consolidados em uma única query SQL para performance)
    kpi_stmt = db.query(
        func.count(MessageDispatchLog.id).label("total"),
        func.sum(case((MessageDispatchLog.status == "SIMULADO", 1), else_=0)).label("simulated"),
        func.sum(case((MessageDispatchLog.status == "RESCHEDULED", 1), else_=0)).label("rescheduled"),
        func.sum(case((MessageDispatchLog.status == "ENVIADO", 1), else_=0)).label("sent"),
        func.sum(case((MessageDispatchLog.status == "FAILED", 1), else_=0)).label("failed")
    ).filter(query.whereclause) # Reaproveita os filtros aplicados anteriormente
    
    kpi_res = kpi_stmt.first()
    kpis = {
        "total": kpi_res.total or 0,
        "simulated": int(kpi_res.simulated or 0),
        "rescheduled": int(kpi_res.rescheduled or 0),
        "sent": int(kpi_res.sent or 0),
        "failed": int(kpi_res.failed or 0),
    }

    # Data
    logs = query.order_by(MessageDispatchLog.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    
    data = []
    for l in logs:
        data.append({
            "id": l.id,
            "created_at": l.created_at.isoformat(),
            "scheduled_for": l.scheduled_for.isoformat() if l.scheduled_for else None,
            "status": l.status,
            "regua_display": f"{l.regua} / {l.gatilho_dias}d",
            "cliente_id": l.customer_id,
            "cliente_nome": l.customer_name,
            "telefone": l.destination_phone,
            "valor": float(l.total_divida or 0),
            "compliance_reason": l.compliance_block_reason or "OK",
            "error": l.error_message,
            "message_rendered": l.message_rendered
        })

    return {
        "data": data,
        "kpis": kpis,
        "meta": {"page": page, "limit": limit}
    }

@router.post("/messages/run-now")
def run_rules_now(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403)
    
    from app.scheduler import run_collection_check
    stats = run_collection_check(SessionLocal)
    msg = f"Execução concluída: {stats['created']} novas, {stats['rescheduled']} reagendadas."
    return RedirectResponse(f"/outbox?msg={msg}", status_code=HTTP_302_FOUND)

@router.get("/api/financeiro/logs")
def get_financial_logs(request: Request, db: Session = Depends(get_db)):
    require_login(request, db)
    logs = db.query(FinancialAlertLog).order_by(FinancialAlertLog.created_at.desc()).limit(50).all()
    return [{
        "id": l.id,
        "created_at": l.created_at.isoformat(),
        "date": l.alert_date.isoformat() if l.alert_date else None,
        "user_name": l.financial_user.name if l.financial_user else "Financeiro",
        "item_count": l.item_count
    } for l in logs]

@router.post("/api/financeiro/run-now")
async def run_financial_now(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403)

    from app.services.notifications import trigger_financial_report
    result = trigger_financial_report(db)
    return {"success": True, "sent_count": result["sent"], "skipped_count": result["skipped"]}

@router.get("/messages", response_class=HTMLResponse)
def messages_list(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    msgs = db.query(SentMessage).order_by(SentMessage.created_at.desc()).limit(200).all()
    return render("messages.html", request=request, user=user, title="Mensagens", messages=msgs)

@router.get("/api/whatsapp/historico")
def get_whatsapp_historico(request: Request, customer_id: int, db: Session = Depends(get_db)):
    require_login(request, db)
    msgs = db.query(WhatsappHistorico).filter(WhatsappHistorico.cliente_id == customer_id).order_by(WhatsappHistorico.created_at.desc()).limit(50).all()
    return [{
        "id": m.id,
        "telefone": m.telefone,
        "mensagem": m.mensagem,
        "tipo": m.tipo,
        "status": m.status,
        "timestamp": m.created_at.isoformat() if m.created_at else None,
    } for m in msgs]
