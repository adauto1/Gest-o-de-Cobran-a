from __future__ import annotations
import logging
from datetime import datetime, timedelta, date
from decimal import Decimal
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.models import (
    CollectionAction, Customer, Installment, User,
    MessageDispatchLog, Campanha, AgingSnapshot, today
)
from app.core.web import render, require_login
from app.core.helpers import format_money

router = APIRouter()
logger = logging.getLogger(__name__)


def _calcular_dados_relatorio(db: Session, de: date, ate: date) -> dict:
    de_dt = datetime.combine(de, datetime.min.time())
    ate_dt = datetime.combine(ate, datetime.max.time())

    # --- Funil do período ---
    contatados = db.query(CollectionAction.customer_id).filter(
        CollectionAction.created_at >= de_dt,
        CollectionAction.created_at <= ate_dt,
    ).distinct().count()

    com_promessa = db.query(CollectionAction.customer_id).filter(
        CollectionAction.created_at >= de_dt,
        CollectionAction.created_at <= ate_dt,
        CollectionAction.outcome == "PROMESSA",
    ).distinct().count()

    pagos = db.query(Installment.customer_id).filter(
        Installment.status == "PAGA",
        Installment.paid_at >= de_dt,
        Installment.paid_at <= ate_dt,
    ).distinct().count()

    recuperado = db.query(func.sum(Installment.amount)).filter(
        Installment.status == "PAGA",
        Installment.paid_at >= de_dt,
        Installment.paid_at <= ate_dt,
    ).scalar() or Decimal(0)

    total_aberto = db.query(func.sum(Installment.open_amount)).filter(
        Installment.status == "ABERTA"
    ).scalar() or Decimal(0)

    # --- Ranking de cobradores ---
    cobradores = db.query(User).filter(User.role == "COBRANCA", User.active == True).all()
    ranking = []
    for u in cobradores:
        cont = db.query(CollectionAction.customer_id).filter(
            CollectionAction.user_id == u.id,
            CollectionAction.created_at >= de_dt,
            CollectionAction.created_at <= ate_dt,
        ).distinct().count()
        prom = db.query(CollectionAction).filter(
            CollectionAction.user_id == u.id,
            CollectionAction.created_at >= de_dt,
            CollectionAction.created_at <= ate_dt,
            CollectionAction.outcome == "PROMESSA",
        ).count()
        val = db.query(func.sum(CollectionAction.promised_amount)).filter(
            CollectionAction.user_id == u.id,
            CollectionAction.created_at >= de_dt,
            CollectionAction.created_at <= ate_dt,
            CollectionAction.outcome == "PROMESSA",
        ).scalar() or Decimal(0)
        ranking.append({
            "nome": u.name,
            "contatados": cont,
            "promessas": prom,
            "valor_prometido": format_money(val),
            "taxa": int(prom / cont * 100) if cont > 0 else 0,
        })
    ranking.sort(key=lambda x: x["promessas"], reverse=True)

    # --- Eficácia da Régua ---
    regua_rows = db.query(
        MessageDispatchLog.regua,
        MessageDispatchLog.gatilho_dias,
        func.count(MessageDispatchLog.id).label("total"),
        func.count(MessageDispatchLog.customer_id.distinct()).label("clientes"),
    ).filter(
        MessageDispatchLog.created_at >= de_dt,
        MessageDispatchLog.created_at <= ate_dt,
        MessageDispatchLog.status.in_(["SENT", "SIMULATED"]),
    ).group_by(MessageDispatchLog.regua, MessageDispatchLog.gatilho_dias).all()

    eficacia = []
    for row in regua_rows:
        # Clientes que prometeram nos 7 dias seguintes ao envio (aproximação)
        prometeram = db.query(CollectionAction.customer_id).filter(
            CollectionAction.outcome == "PROMESSA",
            CollectionAction.created_at >= de_dt,
            CollectionAction.created_at <= ate_dt,
        ).distinct().count()
        taxa = int(prometeram / row.clientes * 100) if row.clientes > 0 else 0
        eficacia.append({
            "regua": row.regua or "—",
            "gatilho_dias": row.gatilho_dias or 0,
            "total_enviados": row.total,
            "clientes": row.clientes,
            "taxa_promessa": taxa,
        })
    eficacia.sort(key=lambda x: x["taxa_promessa"], reverse=True)

    # --- Campanhas ativas no período ---
    campanhas = db.query(Campanha).filter(
        Campanha.ativa == True,
        Campanha.data_inicio <= ate,
        Campanha.data_fim >= de,
    ).all()

    # --- Aging snapshot mais recente ---
    snapshot = db.query(AgingSnapshot).order_by(AgingSnapshot.data.desc()).first()
    aging_hist = []
    snapshots_hist = db.query(AgingSnapshot).order_by(
        AgingSnapshot.data.desc()
    ).limit(7).all()
    for s in reversed(snapshots_hist):
        aging_hist.append({
            "data": s.data.strftime("%d/%m"),
            "v_1_30": format_money(s.v_1_30),
            "v_31_60": format_money(s.v_31_60),
            "v_61_90": format_money(s.v_61_90),
            "v_90plus": format_money(s.v_90plus),
            "c_total": (s.c_1_30 or 0) + (s.c_31_60 or 0) + (s.c_61_90 or 0) + (s.c_90plus or 0),
        })

    return {
        "de": de.strftime("%d/%m/%Y"),
        "ate": ate.strftime("%d/%m/%Y"),
        "funil": {
            "contatados": contatados,
            "com_promessa": com_promessa,
            "pagos": pagos,
            "taxa_contato": int(contatados / max(contatados, 1) * 100),
            "taxa_promessa": int(com_promessa / contatados * 100) if contatados > 0 else 0,
            "taxa_pagamento": int(pagos / com_promessa * 100) if com_promessa > 0 else 0,
        },
        "recuperado": format_money(recuperado),
        "total_aberto": format_money(total_aberto),
        "taxa_recuperacao": int(recuperado / (recuperado + total_aberto) * 100) if (recuperado + total_aberto) > 0 else 0,
        "ranking": ranking[:10],
        "eficacia": eficacia[:10],
        "campanhas": [{"nome": c.nome, "desconto_pct": float(c.desconto_pct or 0),
                       "data_fim": c.data_fim.strftime("%d/%m/%Y")} for c in campanhas],
        "aging_hist": aging_hist,
    }


@router.get("/relatorio", response_class=HTMLResponse)
def relatorio_page(
    request: Request,
    de: str = "",
    ate: str = "",
    db: Session = Depends(get_db)
):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas ADMIN")

    hoje = today()
    try:
        data_de = datetime.strptime(de, "%Y-%m-%d").date() if de else hoje - timedelta(days=30)
        data_ate = datetime.strptime(ate, "%Y-%m-%d").date() if ate else hoje
    except ValueError:
        data_de = hoje - timedelta(days=30)
        data_ate = hoje

    dados = _calcular_dados_relatorio(db, data_de, data_ate)

    return render("relatorio.html", request=request, user=user,
                  title="Relatório Gerencial",
                  active_page="reports",
                  dados=dados,
                  data_de=data_de.strftime("%Y-%m-%d"),
                  data_ate=data_ate.strftime("%Y-%m-%d"))


@router.get("/api/relatorio")
def relatorio_api(
    de: str = "",
    ate: str = "",
    request: Request = None,
    db: Session = Depends(get_db)
):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403)

    hoje = today()
    try:
        data_de = datetime.strptime(de, "%Y-%m-%d").date() if de else hoje - timedelta(days=30)
        data_ate = datetime.strptime(ate, "%Y-%m-%d").date() if ate else hoje
    except ValueError:
        data_de = hoje - timedelta(days=30)
        data_ate = hoje

    return _calcular_dados_relatorio(db, data_de, data_ate)


@router.post("/api/relatorio/enviar-diretores")
async def enviar_relatorio_diretores(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403)

    from app.models import Director
    from app.services.whatsapp import enviar_whatsapp

    hoje = today()
    data_de = hoje - timedelta(days=7)
    dados = _calcular_dados_relatorio(db, data_de, hoje)

    texto = (
        f"📊 *RELATÓRIO SEMANAL — Portal Móveis*\n"
        f"Período: {dados['de']} a {dados['ate']}\n\n"
        f"💰 Recuperado: {dados['recuperado']}\n"
        f"📋 Carteira aberta: {dados['total_aberto']}\n"
        f"📈 Taxa de recuperação: {dados['taxa_recuperacao']}%\n\n"
        f"📞 Funil:\n"
        f"  • Contatados: {dados['funil']['contatados']}\n"
        f"  • Prometeram: {dados['funil']['com_promessa']}\n"
        f"  • Pagaram: {dados['funil']['pagos']}\n\n"
    )
    if dados["ranking"]:
        texto += "🏆 Top cobradores:\n"
        for i, r in enumerate(dados["ranking"][:3], 1):
            texto += f"  {i}. {r['nome']} — {r['promessas']} promessas\n"

    diretores = db.query(Director).filter(Director.active == True).all()
    enviados = 0
    for d in diretores:
        try:
            enviar_whatsapp(d.phone, texto)
            enviados += 1
        except Exception as e:
            logger.warning(f"[Relatório] Falha ao enviar para {d.name}: {e}")

    return {"success": True, "enviados": enviados}
