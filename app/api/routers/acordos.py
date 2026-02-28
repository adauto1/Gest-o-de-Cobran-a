from __future__ import annotations
import logging
from decimal import Decimal
from datetime import datetime as dt
from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Acordo, Customer, today
from app.core.web import require_login

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/api/acordos")
async def criar_acordo(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    dados = await request.json()

    customer_id = int(dados.get("customer_id", 0))
    c = db.get(Customer, customer_id)
    if not c:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    valor_original = Decimal(str(dados.get("valor_original", 0)))
    desconto_pct = Decimal(str(dados.get("desconto_pct", 0))) if dados.get("desconto_pct") else None
    if desconto_pct is not None:
        valor_acordado = valor_original * (1 - desconto_pct / 100)
    else:
        valor_acordado = Decimal(str(dados.get("valor_acordado", valor_original)))

    novo_prazo_str = dados.get("novo_prazo", "")
    try:
        novo_prazo = dt.strptime(novo_prazo_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=422, detail="Data inválida para novo_prazo")

    acordo = Acordo(
        customer_id=customer_id,
        user_id=user.id,
        data_acordo=today(),
        desconto_pct=desconto_pct,
        valor_original=valor_original,
        valor_acordado=valor_acordado,
        novo_prazo=novo_prazo,
        forma_pagamento=str(dados.get("forma_pagamento", "PIX")).upper(),
        status="ATIVO",
        notas=str(dados.get("notas", "")).strip() or None,
    )
    db.add(acordo)
    db.commit()
    db.refresh(acordo)
    return {"success": True, "id": acordo.id, "valor_acordado": float(valor_acordado)}


@router.get("/api/acordos")
def listar_acordos(customer_id: int, request: Request, db: Session = Depends(get_db)):
    require_login(request, db)
    acordos = db.query(Acordo).filter(
        Acordo.customer_id == customer_id
    ).order_by(Acordo.created_at.desc()).all()

    resultado = []
    for a in acordos:
        resultado.append({
            "id": a.id,
            "data_acordo": a.data_acordo.strftime("%d/%m/%Y"),
            "valor_original": float(a.valor_original),
            "desconto_pct": float(a.desconto_pct or 0),
            "valor_acordado": float(a.valor_acordado),
            "novo_prazo": a.novo_prazo.strftime("%d/%m/%Y"),
            "forma_pagamento": a.forma_pagamento,
            "status": a.status,
            "notas": a.notas or "",
            "cobrador": a.user.name if a.user else "—",
        })
    return resultado


@router.post("/api/acordos/{acordo_id}/status")
async def atualizar_status_acordo(acordo_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    dados = await request.json()
    novo_status = str(dados.get("status", "")).upper()
    if novo_status not in ("ATIVO", "CUMPRIDO", "QUEBRADO"):
        raise HTTPException(status_code=422, detail="Status inválido")

    a = db.get(Acordo, acordo_id)
    if not a:
        raise HTTPException(status_code=404)
    a.status = novo_status
    db.commit()
    return {"success": True, "status": novo_status}
