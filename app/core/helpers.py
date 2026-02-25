from decimal import Decimal
from datetime import date
import logging
import re
from typing import List
from urllib.parse import quote
from app.core.config import PRIORITY_CRITICAL_DAYS, PRIORITY_ALERT_DAYS, PRIORITY_MODERATE_DAYS

logger = logging.getLogger(__name__)

def format_money(v) -> str:
    try:
        if v is None: return "R$ 0,00"
        d = Decimal(str(v))
        s = f"{d:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {s}"
    except Exception:
        return "R$ 0,00"

def parse_decimal(v: str) -> Decimal:
    if not v: return Decimal("0")
    s = str(v).strip().replace("R$", "").strip()
    # Padrão BR: "1.250,50" (ambos) ou "1250,50" (só vírgula) ou "1250.50" (só ponto)
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    try:
        return Decimal(s)
    except Exception:
        return Decimal("0")

def parse_date_br(v: str) -> date:
    s = str(v).strip()
    if not s: raise ValueError("Empty date string")
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        y,m,d = s.split("-")
        return date(int(y),int(m),int(d))
    m = re.match(r"^(\d{2})[/-](\d{2})[/-](\d{4})$", s)
    if m:
        d,mo,y = m.groups()
        return date(int(y),int(mo),int(d))
    raise ValueError(f"Invalid date: {v}")

def bucket_priority(max_overdue: int) -> int:
    if max_overdue >= PRIORITY_CRITICAL_DAYS:  return 5
    if max_overdue >= PRIORITY_ALERT_DAYS:     return 4
    if max_overdue >= PRIORITY_MODERATE_DAYS:  return 2
    return 1

def get_regua_nivel(customer_profile: str, max_overdue: int) -> str:
    if customer_profile and customer_profile != "AUTOMATICO":
        return customer_profile
    p = bucket_priority(max_overdue)
    if p >= 5: return "INTENSA"
    if p >= 3: return "MODERADA"
    return "LEVE"

def get_status_label(max_overdue: int) -> str:
    """Retorna o rótulo de status baseado nos dias de atraso. Centraliza lógica duplicada."""
    if max_overdue > 60:
        return "Crítico (>60d)"
    if max_overdue > 30:
        return "Alerta (30d+)"
    if max_overdue > 0:
        return f"{max_overdue} dias atraso"
    return "Em dia"

def wa_link(phone: str, msg: str) -> str:
    if not phone: return ""
    p = "".join(filter(str.isdigit, phone))
    if not p.startswith("55"): p = "55" + p
    return f"https://wa.me/{p}?text={quote(msg)}"

def stores_list(db) -> List[str]:
    from app.models import Customer
    res = db.query(Customer.store).distinct().all()
    return sorted([r[0] for r in res if r[0]])

def rule_for_overdue(db, overdue_days: int, level: str = "LEVE"):
    from app.models import CollectionRule
    rules = db.query(CollectionRule).filter(
        CollectionRule.active == True,
        CollectionRule.level == level
    ).all()
    matched = [r for r in rules if r.start_days <= overdue_days <= r.end_days]
    if not matched:
        return None
    matched.sort(key=lambda r: (r.priority, r.start_days), reverse=True)
    return matched[0]

def get_last_contacts_map(db, customer_ids: List[int]) -> dict:
    """Busca o último contato de todos os clientes em uma única query (evita N+1).
    Retorna {customer_id: "há X dias" ou "Sem contato"}.
    """
    if not customer_ids:
        return {}
    from sqlalchemy import func
    from datetime import datetime
    from app.models import CollectionAction
    subq = db.query(
        CollectionAction.customer_id,
        func.max(CollectionAction.created_at).label("last_contact")
    ).filter(
        CollectionAction.customer_id.in_(customer_ids)
    ).group_by(CollectionAction.customer_id).subquery()

    rows = db.query(subq.c.customer_id, subq.c.last_contact).all()
    result = {}
    today_dt = date.today()
    for row in rows:
        if not row.last_contact:
            continue
        last = row.last_contact
        if isinstance(last, str):
            try:
                last = datetime.fromisoformat(last)
            except Exception:
                result[row.customer_id] = last
                continue
        delta = (today_dt - last.date()).days
        if delta == 0:
            result[row.customer_id] = "hoje"
        elif delta == 1:
            result[row.customer_id] = "há 1 dia"
        else:
            result[row.customer_id] = f"há {delta} dias"
    return result


def get_last_contacts_full_map(db, customer_ids: List[int]) -> dict:
    """Busca o último contato E o outcome de todos os clientes em uma query.
    Retorna {customer_id: {"str": "há X dias", "outcome": "PROMESSA_PAGAMENTO"}}.
    """
    if not customer_ids:
        return {}
    from sqlalchemy import func
    from datetime import datetime
    from app.models import CollectionAction

    # Usa MAX(id) em vez de MAX(created_at) para evitar problemas de precisão
    # de timestamp no SQLite — id é inteiro único e sempre confiável.
    subq = db.query(
        CollectionAction.customer_id,
        func.max(CollectionAction.id).label("last_id")
    ).filter(
        CollectionAction.customer_id.in_(customer_ids)
    ).group_by(CollectionAction.customer_id).subquery()

    rows = db.query(
        subq.c.customer_id,
        CollectionAction.created_at.label("last_contact"),
        CollectionAction.outcome
    ).join(
        CollectionAction,
        (CollectionAction.customer_id == subq.c.customer_id) &
        (CollectionAction.id == subq.c.last_id)
    ).all()

    result = {}
    today_dt = date.today()
    for row in rows:
        if not row.last_contact:
            continue
        last = row.last_contact
        if isinstance(last, str):
            try:
                last = datetime.fromisoformat(last)
            except Exception:
                result[row.customer_id] = {"str": last, "outcome": row.outcome}
                continue
        delta = (today_dt - last.date()).days
        if delta == 0:
            date_str = "hoje"
        elif delta == 1:
            date_str = "há 1 dia"
        else:
            date_str = f"há {delta} dias"
        result[row.customer_id] = {"str": date_str, "outcome": row.outcome or ""}
    return result
