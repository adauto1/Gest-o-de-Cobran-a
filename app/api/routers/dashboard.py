from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict

from app.core.database import get_db
from app.models import Installment, Customer, CollectionAction, User, today, days_overdue
from app.core.web import render, require_login
from app.core.helpers import format_money
from app.api.routers.commissions import calculate_collector_commission

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
            
        # Total a receber (Aberto HOJE + Pago NESSE MÊS de parcelas que venceram naquele mês)
        # Filtro: due_date no mês alvo
        q = db.query(Installment).filter(
            Installment.due_date >= m_start,
            Installment.due_date <= m_end
        )
        if user.role == "COBRANCA" and user.store:
            q = q.join(Customer).filter(Customer.store == user.store)
        
        all_month_insts = q.all()
        
        total_a_receber = Decimal(0)
        valor_atual = Decimal(0)
        
        for i in all_month_insts:
            # Se está aberta, conta no "A Receber"
            if i.status == "ABERTA":
                total_a_receber += i.open_amount
            # Se foi paga, verificamos se foi paga NESSE MÊS
            elif i.status == "PAGA" and i.paid_at:
                if i.paid_at.date() >= start_of_this_month:
                    total_a_receber += i.amount
                    valor_atual += i.amount
        
        target_pct = Decimal("0.70")
        meta_rec = total_a_receber * target_pct
        max_no_rec = total_a_receber * (Decimal(1) - target_pct)
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
            "pct_meta": "70%",
            "pct_atingido_fmt": f"{atingido_pct:,.2f}%",
            "missing_fmt": format_money(missing) if missing > 0 else "R$ 0,00",
            "is_reached": missing <= 0
        })

    return results

@router.get("/dashboard", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)

    q = db.query(Installment).join(Customer).filter(Installment.status == "ABERTA")
    if user.role == "COBRANCA" and user.store:
        q = q.filter(Customer.store == user.store)

    insts = q.all()
    total_open = sum([Decimal(i.open_amount) for i in insts], Decimal("0"))
    
    paid_last_30 = db.query(Installment).filter(Installment.status == "PAGA", Installment.paid_at >= datetime.utcnow() - timedelta(days=30)).all()
    total_paid_30 = sum([Decimal(i.amount) for i in paid_last_30], Decimal("0"))
    
    recovery_rate = (total_paid_30 / (total_paid_30 + total_open)) * 100 if (total_paid_30 + total_open) > 0 else Decimal(0)

    overdue = [i for i in insts if days_overdue(i.due_date) > 0 and Decimal(i.open_amount) > 0]
    total_overdue = sum([Decimal(i.open_amount) for i in overdue], Decimal("0"))

    fiado_percentage = (total_overdue / total_open) * 100 if total_open > 0 else Decimal(0)
    
    due_today_insts = [i for i in insts if days_overdue(i.due_date) == 0 and Decimal(i.open_amount) > 0]
    due_today_total = sum([Decimal(i.open_amount) for i in due_today_insts], Decimal("0"))
    
    upcoming = [i for i in insts if -7 <= days_overdue(i.due_date) < 0 and Decimal(i.open_amount) > 0]
    total_upcoming = sum([Decimal(i.open_amount) for i in upcoming], Decimal("0"))

    aging = {
        "1_30":  {"count": 0, "value": Decimal("0")},
        "31_60": {"count": 0, "value": Decimal("0")},
        "61_90": {"count": 0, "value": Decimal("0")},
        "90_plus": {"count": 0, "value": Decimal("0")},
    }
    urgent_count = 0
    for i in overdue:
        d = days_overdue(i.due_date)
        amt = Decimal(str(i.open_amount))
        if 1 <= d <= 30:
            aging["1_30"]["count"] += 1; aging["1_30"]["value"] += amt
        elif 31 <= d <= 60:
            aging["31_60"]["count"] += 1; aging["31_60"]["value"] += amt
        elif 61 <= d <= 90:
            aging["61_90"]["count"] += 1; aging["61_90"]["value"] += amt
        else:
            aging["90_plus"]["count"] += 1; aging["90_plus"]["value"] += amt
        if d > 60:
            urgent_count += 1

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
            "overdue_installments": len(overdue)
        }

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
                  admin_stats=admin_stats)
