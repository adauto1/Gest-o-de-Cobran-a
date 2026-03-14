from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import CollectionRule
from app.core.web import render, require_admin, get_or_404

router = APIRouter()

@router.get("/rules", response_class=HTMLResponse)
def rules_page(request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    rules = db.query(CollectionRule).order_by(CollectionRule.priority.desc(), CollectionRule.start_days.asc()).all()
    return render("rules.html", request=request, user=user, title="Régua", rules=rules, msg=request.query_params.get("msg"))

@router.post("/rules/{rule_id}/toggle")
def rules_toggle(request: Request, rule_id: int, db: Session = Depends(get_db)):
    require_admin(request, db)
    r = get_or_404(db, CollectionRule, rule_id, "Régua não encontrada")
    r.active = not r.active
    db.commit()
    return RedirectResponse("/rules?msg=Régua atualizada.", status_code=302)

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
    require_admin(request, db)
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
    return RedirectResponse("/rules?msg=Regra criada com sucesso!", status_code=302)
