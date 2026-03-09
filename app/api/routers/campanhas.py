from __future__ import annotations
import logging
from decimal import Decimal
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.models import Campanha, Customer, Installment, today
from app.core.web import render, require_login

router = APIRouter()
logger = logging.getLogger(__name__)


def _count_elegiveis(db: Session, campanha: Campanha) -> int:
    """Conta clientes elegíveis para a campanha com base em dias de atraso e perfil."""
    days_diff = func.julianday(func.date("now")) - func.julianday(Installment.due_date)
    subq = db.query(
        Installment.customer_id,
        func.max(days_diff).label("max_overdue")
    ).filter(
        Installment.status == "ABERTA",
        Installment.open_amount > 0
    ).group_by(Installment.customer_id).subquery()

    q = db.query(Customer).join(subq, Customer.id == subq.c.customer_id).filter(
        subq.c.max_overdue >= campanha.segmento_atraso_min,
        subq.c.max_overdue <= campanha.segmento_atraso_max,
    )
    if campanha.segmento_perfil and campanha.segmento_perfil != "TODOS":
        q = q.filter(Customer.profile_cobranca == campanha.segmento_perfil)
    return q.distinct().count()


@router.get("/campanhas", response_class=HTMLResponse)
def campanhas_page(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas ADMIN")

    campanhas = db.query(Campanha).order_by(Campanha.data_inicio.desc()).all()
    hoje = today()
    campanhas_data = []
    for c in campanhas:
        status = "ENCERRADA"
        if c.ativa and c.data_fim >= hoje:
            status = "ATIVA"
        elif c.ativa and c.data_inicio > hoje:
            status = "AGENDADA"
        campanhas_data.append({
            "obj": c,
            "status": status,
            "elegiveis": _count_elegiveis(db, c),
        })

    return render("campanhas.html", request=request, user=user,
                  title="Campanhas de Cobrança",
                  active_page="campanhas",
                  campanhas=campanhas_data,
                  hoje=hoje.isoformat())


@router.get("/api/campanhas")
def listar_campanhas_api(request: Request, db: Session = Depends(get_db)):
    """Retorna lista de campanhas em JSON para o frontend."""
    require_login(request, db)
    campanhas = db.query(Campanha).order_by(Campanha.data_inicio.desc()).all()
    hoje = today()
    result = []
    for c in campanhas:
        if c.ativa and c.data_inicio <= hoje and c.data_fim >= hoje:
            status = "ATIVA"
        elif c.ativa and c.data_inicio > hoje:
            status = "AGENDADA"
        else:
            status = "ENCERRADA"
        result.append({
            "id": c.id,
            "nome": c.nome,
            "descricao": c.descricao or "",
            "desconto_pct": float(c.desconto_pct or 0),
            "data_inicio": c.data_inicio.strftime("%d/%m/%Y"),
            "data_fim": c.data_fim.strftime("%d/%m/%Y"),
            "segmento_atraso_min": c.segmento_atraso_min,
            "segmento_atraso_max": c.segmento_atraso_max,
            "segmento_perfil": c.segmento_perfil,
            "ativa": c.ativa,
            "status": status,
            "elegiveis": _count_elegiveis(db, c),
        })
    return result


@router.post("/campanhas")
async def criar_campanha(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas ADMIN")

    from datetime import datetime as dt
    dados = await request.json()
    nome = str(dados.get("nome", "")).strip()
    if not nome:
        raise HTTPException(status_code=422, detail="Nome obrigatorio")
    try:
        data_inicio = dt.strptime(dados.get("data_inicio", ""), "%Y-%m-%d").date()
        data_fim = dt.strptime(dados.get("data_fim", ""), "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=422, detail="Datas invalidas. Use YYYY-MM-DD.")
    desconto_raw = dados.get("desconto_pct")
    c = Campanha(
        nome=nome,
        descricao=str(dados.get("descricao", "")).strip() or None,
        desconto_pct=Decimal(str(desconto_raw)) if desconto_raw is not None else None,
        data_inicio=data_inicio,
        data_fim=data_fim,
        segmento_atraso_min=max(0, int(dados.get("segmento_atraso_min", 0))),
        segmento_atraso_max=max(0, int(dados.get("segmento_atraso_max", 9999))),
        segmento_perfil=str(dados.get("segmento_perfil", "TODOS")),
        ativa=True,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return {"success": True, "id": c.id}


@router.post("/campanhas/{campanha_id}/toggle")
def toggle_campanha(campanha_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas ADMIN")
    c = db.get(Campanha, campanha_id)
    if not c:
        raise HTTPException(status_code=404)
    c.ativa = not c.ativa
    db.commit()
    return {"success": True, "ativa": c.ativa}


@router.get("/api/campanhas/{campanha_id}/elegiveis")
def elegiveis(campanha_id: int, request: Request, db: Session = Depends(get_db)):
    require_login(request, db)
    c = db.get(Campanha, campanha_id)
    if not c:
        raise HTTPException(status_code=404)
    return {"count": _count_elegiveis(db, c)}


@router.get("/api/campanhas/ativas")
def campanhas_ativas_api(db: Session = Depends(get_db)):
    """Retorna campanhas ativas para o scheduler usar."""
    hoje = today()
    campanhas = db.query(Campanha).filter(
        Campanha.ativa == True,
        Campanha.data_inicio <= hoje,
        Campanha.data_fim >= hoje,
    ).all()
    return [
        {
            "id": c.id,
            "nome": c.nome,
            "desconto_pct": float(c.desconto_pct or 0),
            "segmento_atraso_min": c.segmento_atraso_min,
            "segmento_atraso_max": c.segmento_atraso_max,
            "segmento_perfil": c.segmento_perfil,
        }
        for c in campanhas
    ]
