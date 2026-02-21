from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict

from app.core.database import get_db
from app.models import Installment, Customer, CollectionAction, User, today, ConferenciaTitulos
from app.core.web import render, require_login
from app.core.helpers import format_money
from app.core.config import RECOVERY_TARGET_PCT
from app.api.routers.commissions import calculate_collector_commission
import json

router = APIRouter()

def calculate_recovery_goals(db: Session, user: User) -> List[Dict]:
    today_dt = today()
    month_names = [
        "JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO",
        "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"
    ]
    
    start_of_this_month = datetime(today_dt.year, today_dt.month, 1).date()
    
    results = []
    # Buckets: 30 (current), 60 (last), 90 (2 months ago)
    buckets = [
        {"label": "30", "offset": 0},
        {"label": "60", "offset": -1},
        {"label": "90", "offset": -2}
    ]

    for b in buckets:
        # Calculate start/end of target month
        target_month = today_dt.month + b["offset"]
        target_year = today_dt.year
        while target_month <= 0:
            target_month += 12
            target_year -= 1
        
        month_name = month_names[target_month - 1]
        
        # Start and End of that specific month
        m_start = datetime(target_year, target_month, 1).date()
        if target_month == 12:
            m_end = datetime(target_year + 1, 1, 1).date() - timedelta(days=1)
        else:
            m_end = datetime(target_year, target_month + 1, 1).date() - timedelta(days=1)
            
        # Total a receber (Otimizado via SQL)
        # Filtro: due_date no mês alvo
        q_base = db.query(Installment).filter(
            Installment.due_date >= m_start,
            Installment.due_date <= m_end
        )
        if user.role == "COBRANCA" and user.store:
            q_base = q_base.join(Customer).filter(Customer.store == user.store)
        
        # Total Aberto HOJE + Pago NESSE MÊS (de parcelas que venceram naquele mês)
        total_a_receber = q_base.filter(
            case(
                (Installment.status == "ABERTA", True),
                ((Installment.status == "PAGA") & (Installment.paid_at >= start_of_this_month), True),
                else_=False
            ) == True
        ).with_entities(func.sum(Installment.amount)).scalar() or Decimal(0)

        valor_atual = q_base.filter(
            Installment.status == "PAGA",
            Installment.paid_at >= start_of_this_month
        ).with_entities(func.sum(Installment.amount)).scalar() or Decimal(0)
        
        meta_rec = total_a_receber * RECOVERY_TARGET_PCT
        max_no_rec = total_a_receber * (Decimal(1) - RECOVERY_TARGET_PCT)
        missing = meta_rec - valor_atual
        atingido_pct = (valor_atual / total_a_receber * 100) if total_a_receber > 0 else Decimal(0)

        results.append({
            "is_current": b["offset"] == 0,
            "month_name": month_name,
            "carteira": b["label"],
            "total_rec_fmt": format_money(total_a_receber),
            "meta_rec_fmt": format_money(meta_rec),
            "max_no_rec_fmt": format_money(max_no_rec),
            "valor_atual_fmt": format_money(valor_atual),
            "pct_meta": f"{RECOVERY_TARGET_PCT * 100:.0f}%",
            "pct_atingido_fmt": f"{atingido_pct:,.2f}%",
            "missing_fmt": format_money(missing) if missing > 0 else "R$ 0,00",
            "is_reached": missing <= 0
        })

    return results

@router.get("/dashboard", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)

    # --- Estatísticas Globais (Otimizadas via SQL) ---
    total_open = db.query(func.sum(Installment.open_amount)).filter(Installment.status == "ABERTA")
    if user.role == "COBRANCA" and user.store:
        total_open = total_open.join(Customer).filter(Customer.store == user.store)
    total_open = total_open.scalar() or Decimal("0")
    
    # Recebimentos últimos 30 dias
    last_30 = datetime.utcnow() - timedelta(days=30)
    total_paid_30 = db.query(func.sum(Installment.amount)).filter(
        Installment.status == "PAGA", 
        Installment.paid_at >= last_30
    ).scalar() or Decimal("0")
    
    recovery_rate = (total_paid_30 / (total_paid_30 + total_open)) * 100 if (total_paid_30 + total_open) > 0 else Decimal(0)

    # Vencidos e Hoje
    dt_today = today()
    total_overdue = db.query(func.sum(Installment.open_amount)).filter(
        Installment.status == "ABERTA",
        Installment.due_date < dt_today
    )
    if user.role == "COBRANCA" and user.store:
        total_overdue = total_overdue.join(Customer).filter(Customer.store == user.store)
    total_overdue = total_overdue.scalar() or Decimal("0")

    fiado_percentage = (total_overdue / total_open) * 100 if total_open > 0 else Decimal(0)
    
    due_today_total = db.query(func.sum(Installment.open_amount)).filter(
        Installment.status == "ABERTA",
        Installment.due_date == dt_today
    )
    if user.role == "COBRANCA" and user.store:
        due_today_total = due_today_total.join(Customer).filter(Customer.store == user.store)
    due_today_total = due_today_total.scalar() or Decimal("0")
    
    next_7 = dt_today + timedelta(days=7)
    total_upcoming = db.query(func.sum(Installment.open_amount)).filter(
        Installment.status == "ABERTA",
        Installment.due_date > dt_today,
        Installment.due_date <= next_7
    )
    if user.role == "COBRANCA" and user.store:
        total_upcoming = total_upcoming.join(Customer).filter(Customer.store == user.store)
    total_upcoming = total_upcoming.scalar() or Decimal("0")

    # Aging (Otimizado com Case/When)
    aging_query = db.query(
        func.count(Installment.id).label("count"),
        func.sum(Installment.open_amount).label("value"),
        case(
            (Installment.due_date >= dt_today - timedelta(days=30), "1_30"),
            (Installment.due_date >= dt_today - timedelta(days=60), "31_60"),
            (Installment.due_date >= dt_today - timedelta(days=90), "61_90"),
            else_="90_plus"
        ).label("range")
    ).filter(Installment.status == "ABERTA", Installment.due_date < dt_today)
    
    if user.role == "COBRANCA" and user.store:
        aging_query = aging_query.join(Customer).filter(Customer.store == user.store)
        
    aging_results = aging_query.group_by("range").all()
    
    aging = {
        "1_30":  {"count": 0, "value": Decimal("0")},
        "31_60": {"count": 0, "value": Decimal("0")},
        "61_90": {"count": 0, "value": Decimal("0")},
        "90_plus": {"count": 0, "value": Decimal("0")},
    }
    urgent_count = 0
    for r in aging_results:
        aging[r.range]["count"] = r.count
        aging[r.range]["value"] = r.value or Decimal("0")
        if r.range in ["61_90", "90_plus"]:
            urgent_count += r.count

    for k in aging:
        aging[k]["value_fmt"] = format_money(aging[k]["value"])

    promises = db.query(CollectionAction).filter(CollectionAction.promised_date == today()).order_by(CollectionAction.created_at.desc()).limit(10).all()

    current_commission = "R$ 0,00"
    if user.role == "COBRANCA":
        comm_data = calculate_collector_commission(db, user.id, "30", today().year, today().month)
        current_commission = format_money(comm_data["commission_value"])

    admin_stats = {}
    if user.role == "ADMIN":
        admin_stats = {
            "customers": db.query(Customer).count(),
            "total_installments": db.query(Installment).count(),
            "open_installments": db.query(Installment).filter(Installment.status == "ABERTA").count(),
            "overdue_installments": db.query(Installment).filter(Installment.status == "ABERTA", Installment.due_date < dt_today).count()
        }


    # Smart Reconciliation Data
    smart_recon = db.query(ConferenciaTitulos).order_by(ConferenciaTitulos.data_processamento.desc()).first()
    smart_data = None
    if smart_recon:
        smart_data = json.loads(smart_recon.resumo_json)
        smart_data["data"] = smart_recon.data_processamento.strftime("%d/%m/%Y %H:%M")

    return render("dashboard.html", request=request, user=user, title="Dashboard",
                  total_open=format_money(total_open),
                  total_overdue=format_money(total_overdue),
                  total_upcoming=format_money(total_upcoming),
                  due_today_total=due_today_total,
                  aging=aging, urgent_count=urgent_count,
                  promises=promises, today=today().isoformat(),
                  recovery_rate=recovery_rate,
                  fiado_percentage=fiado_percentage,
                  recovery_goals=calculate_recovery_goals(db, user),
                  current_commission=current_commission,
                  admin_stats=admin_stats,
                  smart_data=smart_data)
