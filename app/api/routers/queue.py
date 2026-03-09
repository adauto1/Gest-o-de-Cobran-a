import logging
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, case, or_, and_
from decimal import Decimal
from datetime import timedelta
from typing import Optional

from app.core.database import get_db
from app.models import Customer, Installment, today
from app.core.web import render, require_login
from app.core.helpers import get_regua_nivel, bucket_priority, stores_list, get_status_label, get_last_contacts_full_map, get_scores_batch
from app.schemas import PriorityQueueResponse, PriorityQueueItem, QueueStats

router = APIRouter()
logger = logging.getLogger(__name__)


def _build_overdue_subquery(db: Session, filters: list):
    """Monta a subquery de agregação de parcelas em aberto."""
    days_diff_expr = func.julianday(func.date('now')) - func.julianday(Installment.due_date)
    return db.query(
        Installment.customer_id,
        func.max(days_diff_expr).label("max_overdue_days"),
        func.sum(Installment.open_amount).label("total_open_val"),
        func.count(Installment.id).label("count_open_val")
    ).filter(*filters).group_by(Installment.customer_id).subquery()


def _apply_user_filters(query, _stmt, user, db: Session):
    """Aplica filtros de acesso por role e loja."""
    if user.role == "COBRANCA":
        if user.store:
            query = query.filter(Customer.store == user.store)
        assigned_exist = db.query(Customer).filter(Customer.assigned_to_user_id != None).count() > 0
        if assigned_exist:
            query = query.filter(Customer.assigned_to_user_id == user.id)
    return query



@router.get("/api/fila/prioridade", response_model=PriorityQueueResponse)
def get_priority_queue_api(
    request: Request,
    page: int = 1,
    limit: int = 30,
    regua: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Endpoint AJAX usado pelo dashboard para carregar a fila de prioridade."""
    logger.info(f"[fila/prioridade] page={page}, limit={limit}, regua={regua}")
    user = require_login(request, db)

    if page < 1:
        page = 1
    offset = (page - 1) * limit

    base_filters = [Installment.status == "ABERTA", Installment.open_amount > 0]
    stmt = _build_overdue_subquery(db, base_filters)

    query = db.query(Customer, stmt.c.max_overdue_days, stmt.c.total_open_val, stmt.c.count_open_val)\
        .join(stmt, Customer.id == stmt.c.customer_id)
    query = _apply_user_filters(query, stmt, user, db)

    # Filtro por nível de régua
    if regua in ("LEVE", "MODERADA", "INTENSA"):
        auto_cond = or_(
            Customer.profile_cobranca == None,
            Customer.profile_cobranca == "",
            Customer.profile_cobranca == "AUTOMATICO"
        )
        if regua == "INTENSA":
            query = query.filter(or_(
                Customer.profile_cobranca == "INTENSA",
                and_(auto_cond, stmt.c.max_overdue_days >= 60)
            ))
        elif regua == "MODERADA":
            query = query.filter(or_(
                Customer.profile_cobranca == "MODERADA",
                and_(auto_cond, stmt.c.max_overdue_days >= 30, stmt.c.max_overdue_days < 60)
            ))
        else:  # LEVE
            query = query.filter(or_(
                Customer.profile_cobranca == "LEVE",
                and_(auto_cond, stmt.c.max_overdue_days < 30)
            ))

    prio_case = case(
        (stmt.c.max_overdue_days >= 30, 3),
        (stmt.c.max_overdue_days >= 5, 2),
        else_=1
    )
    query = query.order_by(prio_case.desc(), stmt.c.max_overdue_days.desc(), stmt.c.total_open_val.desc())

    total_items = query.count()
    total_pages = (total_items + limit - 1) // limit
    results = query.offset(offset).limit(limit).all()

    # Busca últimos contatos + outcome de uma vez (sem N+1)
    customer_ids = [row[0].id for row in results]
    last_contacts = get_last_contacts_full_map(db, customer_ids)

    # Score de propensão ao pagamento em lote (sem N+1)
    customers_map = {row[0].id: row[0] for row in results}
    scores = get_scores_batch(db, customer_ids, customers_map)

    # Calcula stats da carteira para o usuário atual
    from app.models import CollectionAction
    from datetime import datetime
    today_start = datetime.combine(today(), datetime.min.time())

    all_ids_query = db.query(Customer.id).join(stmt, Customer.id == stmt.c.customer_id)
    all_ids_query = _apply_user_filters(all_ids_query, stmt, user, db)
    all_customer_ids = [r[0] for r in all_ids_query.all()]

    sem_contato_hoje = 0
    promessas_abertas = 0
    if all_customer_ids:
        contatados_hoje = db.query(CollectionAction.customer_id).filter(
            CollectionAction.customer_id.in_(all_customer_ids),
            CollectionAction.created_at >= today_start
        ).distinct().count()
        sem_contato_hoje = len(all_customer_ids) - contatados_hoje
        promessas_abertas = db.query(CollectionAction.customer_id).filter(
            CollectionAction.customer_id.in_(all_customer_ids),
            CollectionAction.outcome == "PROMESSA",
            or_(CollectionAction.promised_date == None, CollectionAction.promised_date >= today())
        ).distinct().count()

    stats = QueueStats(
        total_carteira=total_items,
        sem_contato_hoje=max(0, sem_contato_hoje),
        promessas_abertas=promessas_abertas
    )

    items = []
    for row in results:
        cust, mo, to, co = row
        max_over = int(mo) if mo else 0
        contato_info = last_contacts.get(cust.id, {})
        ultimo_contato_str = contato_info.get("str", "Sem contato") if contato_info else "Sem contato"
        ultimo_outcome = contato_info.get("outcome", None) if contato_info else None

        items.append(PriorityQueueItem(
            cliente_id=cust.id,
            nome_cliente=cust.name,
            phone=cust.whatsapp or "",
            valor_em_aberto=float(to or 0),
            max_atraso=max_over,
            data_vencimento=(today() - timedelta(days=max_over)).strftime("%d/%m/%Y") if mo is not None else "",
            profile_cobranca=cust.profile_cobranca,
            ultimo_contato_str=ultimo_contato_str,
            ultimo_outcome=ultimo_outcome,
            qtd_parcelas=co,
            status_label=get_status_label(max_over),
            regua_nivel=get_regua_nivel(cust.profile_cobranca, max_over),
            perfil_devedor=getattr(cust, "perfil_devedor", None) or "NORMAL",
            score_propensao=scores.get(cust.id, 50)
        ))

    return PriorityQueueResponse(
        items=items,
        total_items=total_items,
        total_pages=total_pages,
        current_page=page,
        stats=stats
    )


@router.get("/queue", response_class=HTMLResponse)
def queue_page(
    request: Request,
    store: Optional[str] = None,
    filtro_atraso: Optional[str] = None,
    tab: Optional[str] = None,
    page: int = 1,
    db: Session = Depends(get_db)
):
    user = require_login(request, db)

    page_size = 20
    if page < 1:
        page = 1
    offset = (page - 1) * page_size

    days_diff_expr = func.julianday(func.date('now')) - func.julianday(Installment.due_date)

    base_filters = [Installment.status == "ABERTA", Installment.open_amount > 0]
    if tab == "due_today":
        base_filters.append(days_diff_expr == 0)

    stmt = db.query(
        Installment.customer_id,
        func.max(days_diff_expr).label("max_overdue_days"),
        func.sum(Installment.open_amount).label("total_open_val"),
        func.count(Installment.id).label("count_open_val")
    ).filter(*base_filters)

    if tab == "overdue":
        stmt = stmt.having(func.max(days_diff_expr) > 0)

    stmt = stmt.group_by(Installment.customer_id).subquery()

    query = db.query(Customer, stmt.c.max_overdue_days, stmt.c.total_open_val, stmt.c.count_open_val)\
        .join(stmt, Customer.id == stmt.c.customer_id)

    filtro_label = None
    FILTRO_MAP = {
        "1-30":   (1, 30,  "1-30 dias de atraso"),
        "31-60":  (31, 60, "31-60 dias de atraso"),
        "61-90":  (61, 90, "61-90 dias de atraso"),
    }
    if filtro_atraso in FILTRO_MAP:
        lo, hi, filtro_label = FILTRO_MAP[filtro_atraso]
        query = query.filter(stmt.c.max_overdue_days >= lo, stmt.c.max_overdue_days <= hi)
    elif filtro_atraso == "90-plus":
        query = query.filter(stmt.c.max_overdue_days > 90)
        filtro_label = "+90 dias de atraso"

    query = _apply_user_filters(query, stmt, user, db)

    if store:
        query = query.filter(Customer.store == store)

    prio_case = case(
        (stmt.c.max_overdue_days >= 30, 3),
        (stmt.c.max_overdue_days >= 5, 2),
        else_=1
    )
    query = query.order_by(prio_case.desc(), stmt.c.max_overdue_days.desc(), stmt.c.total_open_val.desc())

    total_items = query.count()
    total_pages = (total_items + page_size - 1) // page_size
    results = query.offset(offset).limit(page_size).all()

    # Busca últimos contatos + outcome de uma vez (sem N+1)
    customer_ids = [row[0].id for row in results]
    last_contacts = get_last_contacts_full_map(db, customer_ids)

    items = []
    for row in results:
        cust, mo, to, co = row
        max_over = int(mo) if mo else 0
        contato_info = last_contacts.get(cust.id, {})
        ultimo_contato_str = contato_info.get("str", "Sem contato") if contato_info else "Sem contato"
        ultimo_outcome = contato_info.get("outcome", None) if contato_info else None
        items.append({
            "customer": cust,
            "max_overdue": max_over,
            "priority": bucket_priority(max_over),
            "total_open": Decimal(to) if to else Decimal(0),
            "count_open": co,
            "regua_nivel": get_regua_nivel(cust.profile_cobranca, max_over),
            "status_label": get_status_label(max_over),
            "ultimo_contato_str": ultimo_contato_str,
            "ultimo_outcome": ultimo_outcome,
            "perfil_devedor": getattr(cust, "perfil_devedor", None) or "NORMAL",
            "data_vencimento": (today() - timedelta(days=max_over)).isoformat()
        })

    return render("queue.html", request=request, user=user, title="Fila de Cobrança",
                  items=items,
                  stores=stores_list(db),
                  selected_store=store or "",
                  tab=tab,
                  page=page,
                  total_pages=total_pages,
                  filtro_ativo=filtro_label)
