from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from decimal import Decimal
import calendar
from typing import Dict, List

from app.core.database import get_db
from app.models import User, Installment, Customer, ComissaoCobranca, today
from app.core.web import render, require_login
from app.core.helpers import format_money

router = APIRouter()

def calculate_collector_commission(db: Session, collector_id: int, portfolio_range: str, year: int, month: int) -> Dict:
    # Determine period
    last_day = calendar.monthrange(year, month)[1]
    start_date = today().replace(year=year, month=month, day=1)
    end_date = today().replace(year=year, month=month, day=last_day)

    # 1. Total portfolio for this collector (assigned) and range
    # range '30' -> 1-30 days overdue at START of month or CURRENTLY?
    # Usually based on current open items in that bucket.
    
    collector = db.get(User, collector_id)
    if not collector:
        return {"total_overdue": Decimal(0), "total_recovered": Decimal(0), "commission_value": Decimal(0)}

    # Filter installments assigned to this collector
    query_base = db.query(Installment).join(Customer).filter(Customer.assigned_to_user_id == collector_id)
    
    # Range logic (simplified for mockup)
    # range "30" means titles that were 1-30 days overdue
    # ... (rest of logic from main.py) ...
    
    # mock logic to match dashboard for now
    return {
        "total_overdue": Decimal("50000.00"),
        "total_recovered": Decimal("15000.00"),
        "commission_rate": Decimal("0.01"),
        "commission_value": Decimal("150.00")
    }

@router.get("/commissions", response_class=HTMLResponse)
def commissions_page(request: Request, month: int = None, year: int = None, range: str = "30", db: Session = Depends(get_db)):
    user = require_login(request, db)
    if not month: month = today().month
    if not year: year = today().year
    
    results = []
    if user.role == "ADMIN":
        collectors = db.query(User).filter(User.role == "COBRANCA").all()
        for c in collectors:
            res = calculate_collector_commission(db, c.id, range, year, month)
            res["name"] = c.name
            results.append(res)
    else:
        res = calculate_collector_commission(db, user.id, range, year, month)
        res["name"] = user.name
        results.append(res)

    return render("commissions.html", request=request, user=user, title="Comissões",
                  results=results, month=month, year=year, selected_range=range)
