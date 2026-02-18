from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional, List

from app.core.database import get_db
from app.models import CollectionRule
from app.core.web import render, require_login
from app.core.helpers import rule_for_overdue

router = APIRouter()

@router.get("/rules", response_class=HTMLResponse)
def rules_page(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas ADMIN")
    rules = db.query(CollectionRule).order_by(CollectionRule.priority.desc(), CollectionRule.start_days.asc()).all()
    return render("rules.html", request=request, user=user, title="Régua", rules=rules, msg=request.query_params.get("msg"))

@router.post("/rules/{rule_id}/toggle")
def rules_toggle(request: Request, rule_id: int, db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas ADMIN")
    r = db.get(CollectionRule, rule_id)
    if not r:
        raise HTTPException(status_code=404, detail="Régua não encontrada")
    r.active = not r.active
    db.commit()
    return RedirectResponse("/rules?msg=Régua atualizada.", status_code=HTTP_302_FOUND)

@router.post("/rules")
def rules_create(
    request: Request,
    start_days: int = Form(...),
    end_days: int = Form(...),
    priority: int = Form(...),
    level: str = Form("LEVE"),
    default_action: str = Form(...),
    template_message: str = Form(...),
    frequency: int = Form(1),
    db: Session = Depends(get_db)
):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas ADMIN")
    db.add(CollectionRule(
        start_days=start_days,
        end_days=end_days,
        priority=priority,
        level=level,
        default_action=default_action.strip().upper(),
        template_message=template_message.strip(),
        frequency=frequency,
        active=True
    ))
    db.commit()
    return RedirectResponse("/rules?msg=Regra criada com sucesso!", status_code=HTTP_302_FOUND)
