from __future__ import annotations
import logging
from datetime import datetime as dt, date
from collections import defaultdict
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import CollectionAction, Customer, today
from app.core.web import render, require_login

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/promessas", response_class=HTMLResponse)
def promessas_page(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    return render("promessas.html", request=request, user=user,
                  title="Calendário de Promessas",
                  active_page="promessas")


@router.get("/api/promessas/mes")
def promessas_mes(mes: str = "", request: Request = None, db: Session = Depends(get_db)):
    """Retorna promessas agrupadas por dia para o mês indicado (YYYY-MM)."""
    require_login(request, db)

    hoje = today()
    if not mes:
        mes = hoje.strftime("%Y-%m")

    try:
        ano, mês_n = int(mes.split("-")[0]), int(mes.split("-")[1])
    except Exception:
        return {}

    mes_inicio = date(ano, mês_n, 1)
    if mês_n == 12:
        mes_fim = date(ano + 1, 1, 1)
    else:
        mes_fim = date(ano, mês_n + 1, 1)

    # Busca todas as promessas do mês com dados do cliente
    rows = db.query(CollectionAction, Customer).join(
        Customer, CollectionAction.customer_id == Customer.id
    ).filter(
        CollectionAction.outcome == "PROMESSA",
        CollectionAction.promised_date >= mes_inicio,
        CollectionAction.promised_date < mes_fim,
    ).order_by(CollectionAction.promised_date).all()

    # Verificar quais foram cumpridas/não cumpridas
    # Uma promessa é cumprida se existe ação posterior com PROMESSA_PAGAMENTO ou PAGOU
    cumpridas_ids: set = set()
    nao_cumpridas_ids: set = set()
    customer_ids = list({r.CollectionAction.customer_id for r in rows})
    if customer_ids:
        acoes_post = db.query(CollectionAction).filter(
            CollectionAction.customer_id.in_(customer_ids),
            CollectionAction.outcome.in_(["PROMESSA_PAGAMENTO", "PAGOU", "PROMESSA_NAO_CUMPRIDA"])
        ).all()
        for a in acoes_post:
            if a.outcome in ("PROMESSA_PAGAMENTO", "PAGOU"):
                cumpridas_ids.add(a.customer_id)
            elif a.outcome == "PROMESSA_NAO_CUMPRIDA":
                nao_cumpridas_ids.add(a.customer_id)

    por_dia: dict = defaultdict(lambda: {"count": 0, "valor_total": 0.0, "clientes": []})
    for r in rows:
        acao = r.CollectionAction
        cliente = r.Customer
        dia_str = acao.promised_date.strftime("%Y-%m-%d")

        if acao.customer_id in cumpridas_ids:
            status_p = "CUMPRIDA"
        elif acao.customer_id in nao_cumpridas_ids:
            status_p = "NAO_CUMPRIDA"
        elif acao.promised_date and acao.promised_date < hoje:
            status_p = "VENCIDA"
        else:
            status_p = "PENDENTE"

        por_dia[dia_str]["count"] += 1
        por_dia[dia_str]["valor_total"] += float(acao.promised_amount or 0)
        por_dia[dia_str]["clientes"].append({
            "id": cliente.id,
            "nome": cliente.name,
            "telefone": cliente.whatsapp or "",
            "valor": float(acao.promised_amount or 0),
            "status_promessa": status_p,
        })

    return dict(por_dia)
