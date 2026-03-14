import logging
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime
from starlette.status import HTTP_302_FOUND

from app.core.database import get_db
from app.models import Customer, CollectionAction
from app.core.web import require_login, get_or_404
from app.core.helpers import parse_decimal
from app.schemas import CollectionActionCreate

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/api/collection-actions")
def create_action_ajax(request: Request, action_data: CollectionActionCreate, db: Session = Depends(get_db)):
    user = require_login(request, db)
    c = get_or_404(db, Customer, action_data.customer_id, "Cliente não encontrado")

    action = CollectionAction(
        customer_id=c.id,
        user_id=user.id,
        action_type=action_data.action_type.upper(),
        outcome=action_data.outcome.upper(),
        notes=(action_data.notes or "").strip(),
        promised_date=action_data.promised_date,
        promised_amount=action_data.promised_amount
    )
    db.add(action)
    db.commit()
    return {"success": True, "message": "Ação registrada com sucesso!"}

@router.post("/actions")
def create_action(
    request: Request,
    customer_id: int = Form(...),
    action_type: str = Form(...),
    outcome: str = Form(...),
    notes: str = Form(""),
    promised_date: str = Form(""),
    promised_amount: str = Form(""),
    db: Session = Depends(get_db)
):
    user = require_login(request, db)
    c = get_or_404(db, Customer, customer_id, "Cliente não encontrado")

    p_date = None
    if promised_date:
        try:
            p_date = datetime.strptime(promised_date, "%Y-%m-%d").date()
        except ValueError:
            logger.warning(f"Data inválida recebida: {promised_date!r}")

    p_amt = parse_decimal(promised_amount) if promised_amount else None

    action = CollectionAction(
        customer_id=c.id,
        user_id=user.id,
        action_type=action_type.upper(),
        outcome=outcome.upper(),
        notes=notes.strip(),
        promised_date=p_date,
        promised_amount=p_amt
    )
    db.add(action)
    db.commit()

    return RedirectResponse(f"/customers/{customer_id}?msg=Ação registrada!", status_code=HTTP_302_FOUND)
