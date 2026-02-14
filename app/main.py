
from __future__ import annotations

import csv
import io
import os
import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict

from fastapi import FastAPI, Request, Depends, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.status import HTTP_302_FOUND

from sqlalchemy import (
    create_engine, Column, Integer, String, Date, DateTime, Boolean,
    ForeignKey, Numeric, Text, Index
)
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, Session

from passlib.context import CryptContext
from jinja2 import Environment, FileSystemLoader, select_autoescape

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
DATA_DIR = os.getenv("DATA_DIR", "./data")
os.makedirs(DATA_DIR, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR}/app.db")
SECRET_KEY = os.getenv("SESSION_SECRET", "CHANGE-ME-IN-PROD")
DEFAULT_ADMIN_EMAIL = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@portalmoveis.local")
DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")
APP_TITLE = os.getenv("APP_TITLE", "Gestor de Cobrança — Portal Móveis")
APP_VERSION = os.getenv("APP_VERSION", "4.0")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    email = Column(String(190), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="ADMIN")  # ADMIN/COBRANCA
    store = Column(String(80), nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True)
    external_key = Column(String(190), unique=True, nullable=False)
    name = Column(String(190), nullable=False)
    cpf_cnpj = Column(String(40), nullable=True)
    whatsapp = Column(String(40), nullable=True)
    store = Column(String(80), nullable=True)
    address = Column(String(255), nullable=True)
    assigned_to_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    assigned_to = relationship("User")
    installments = relationship("Installment", back_populates="customer", cascade="all, delete-orphan")
    actions = relationship("CollectionAction", back_populates="customer", cascade="all, delete-orphan")

class Installment(Base):
    __tablename__ = "installments"
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    contract_id = Column(String(120), nullable=False)
    installment_number = Column(Integer, nullable=False, default=1)
    issue_date = Column(Date, nullable=True)
    due_date = Column(Date, nullable=False)
    amount = Column(Numeric(12,2), nullable=False)
    open_amount = Column(Numeric(12,2), nullable=False)
    status = Column(String(20), nullable=False, default="ABERTA")
    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="installments")

Index("ix_installments_due_date", Installment.due_date)
Index("ix_installments_status", Installment.status)
Index("ix_installments_contract_id", Installment.contract_id)
Index("ix_installments_customer_id", Installment.customer_id)

class CollectionAction(Base):
    __tablename__ = "collection_actions"
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    installment_id = Column(Integer, ForeignKey("installments.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action_type = Column(String(20), nullable=False)
    outcome = Column(String(120), nullable=False)
    notes = Column(Text, nullable=True)
    promised_date = Column(Date, nullable=True)
    promised_amount = Column(Numeric(12, 2), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="actions")
    user = relationship("User")


class CollectionRule(Base):
    __tablename__ = "collection_rules"
    id = Column(Integer, primary_key=True)
    level = Column(String(20), nullable=False, default="LEVE")  # LEVE, MODERADA, INTENSA
    start_days = Column(Integer, nullable=False)
    end_days = Column(Integer, nullable=False)
    default_action = Column(String(20), nullable=False, default="WHATSAPP")
    template_message = Column(Text, nullable=False, default="")
    frequency = Column(Integer, nullable=False, default=1)
    priority = Column(Integer, nullable=False, default=1)
    active = Column(Boolean, default=True)


class SentMessage(Base):
    __tablename__ = "sent_messages"
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    rule_id = Column(Integer, ForeignKey("collection_rules.id"), nullable=True)
    channel = Column(String(20), nullable=False)  # WHATSAPP, CALL, EMAIL
    template_used = Column(Text, nullable=True)
    message_body = Column(Text, nullable=True)
    phone = Column(String(40), nullable=True)
    status = Column(String(20), nullable=False, default="SIMULADO")  # SIMULADO, PENDENTE, ENVIADO, FALHA
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer")
    user = relationship("User")
    rule = relationship("CollectionRule")


class ComissaoCobranca(Base):
    __tablename__ = "comissoes_cobranca"
    id = Column(Integer, primary_key=True)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    store = Column(String(80), nullable=True)
    portfolio_range = Column(String(20), nullable=False) # 30, 60, 90
    total_receivable = Column(Numeric(12, 2), nullable=False)
    recovery_goal = Column(Numeric(12, 2), nullable=False)
    actual_recovered = Column(Numeric(12, 2), nullable=False)
    achieved_percent = Column(Numeric(12, 2), nullable=False)
    commission_percent = Column(Numeric(5, 2), nullable=False)
    commission_value = Column(Numeric(12, 2), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")



# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def format_money(v) -> str:
    try:
        d = Decimal(v)
        s = f"{d:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {s}"
    except:
        return "R$ 0,00"

# -----------------------------------------------------------------------------
# Templating
# -----------------------------------------------------------------------------
env = Environment(
    loader=FileSystemLoader("app/templates"),
    autoescape=select_autoescape(["html", "xml"])
)
env.filters["brl"] = format_money

PAGE_MAP = {
    "dashboard.html": ("dashboard", "Dashboard"),
    "queue.html": ("queue", "Fila do Dia"),
    "customers.html": ("customers", "Clientes"),
    "customer.html": ("customers", "Detalhe do Cliente"),
    "import.html": ("import", "Importar Dados"),
    "rules.html": ("rules", "Régua de Cobrança"),
    "users.html": ("users", "Usuários"),
    "commissions.html": ("commissions", "Comissão"),
    "messages.html": ("messages", "Mensagens"),
}

def render(template: str, **ctx):
    page_info = PAGE_MAP.get(template, ("", ""))
    ctx.setdefault("active_page", page_info[0])
    ctx.setdefault("page_title", page_info[1])
    tpl = env.get_template(template)
    return HTMLResponse(tpl.render(**ctx))

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_password(p: str) -> str:
    return pwd_context.hash(p)

def verify_password(p: str, h: str) -> bool:
    return pwd_context.verify(p, h)

def require_login(request: Request, db: Session) -> User:
    uid = request.session.get("uid")
    if not uid:
        raise HTTPException(status_code=401, detail="Not logged in")
    user = db.get(User, uid)
    if not user or not user.active:
        raise HTTPException(status_code=401, detail="Invalid user")
    return user

def parse_decimal(v: str) -> Decimal:
    s = str(v).strip().replace("R$", "").strip()
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    return Decimal(s or "0")

def parse_date(v: str) -> date:
    s = str(v).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        y,m,d = s.split("-")
        return date(int(y),int(m),int(d))
    m = re.match(r"^(\d{2})[/-](\d{2})[/-](\d{4})$", s)
    if m:
        d,mo,y = m.groups()
        return date(int(y),int(mo),int(d))
    raise ValueError(f"Invalid date: {v}")

def today() -> date:
    return datetime.utcnow().date()

def days_overdue(due: date) -> int:
    return (today() - due).days

def bucket_priority(max_overdue: int) -> int:
    if max_overdue >= 60: return 5
    if max_overdue >= 30: return 4
    if max_overdue >= 15: return 3
    if max_overdue >= 5:  return 2
    if max_overdue >= 0:  return 1
    return 0

def rule_for_overdue(db: Session, overdue_days: int) -> Optional[CollectionRule]:
    rules = db.query(CollectionRule).filter(CollectionRule.active == True).all()
    matched = [r for r in rules if r.start_days <= overdue_days <= r.end_days]
    if not matched:
        return None
    matched.sort(key=lambda r: (r.priority, r.start_days), reverse=True)
    return matched[0]


def wa_link(phone: Optional[str], message: str) -> Optional[str]:
    if not phone:
        return None
    digits = "".join([c for c in phone if c.isdigit()])
    if len(digits) <= 11 and not digits.startswith("55"):
        digits = "55" + digits
    import urllib.parse
    return f"https://wa.me/{digits}?text={urllib.parse.quote(message)}"

def stores_list(db: Session) -> List[str]:
    return sorted({(c.store or "").strip() for c in db.query(Customer).all() if (c.store or "").strip()})

def calculate_collector_commission(db: Session, collector_id: int, portfolio_range: str, year: int, month: int):
    # Determine period
    import calendar
    _, last_day = calendar.monthrange(year, month)
    p_start = date(year, month, 1)
    p_end = date(year, month, last_day)

    # Filter installments by collector assignment and portfolio range
    # Portfolio range logic: e.g. "30" means installments due within 30 days of delay relative to start of calculation
    # For simplicity, we filter installments where delay <= range
    max_days = int(portfolio_range) if portfolio_range.isdigit() else 9999
    
    query = db.query(Installment).join(Customer).filter(Customer.assigned_to_user_id == collector_id)
    all_insts = query.all()
    
    # Total Receivable: All installments in that range (Open + Paid)
    target_insts = [i for i in all_insts if days_overdue(i.due_date) <= max_days]
    total_receivable = sum([Decimal(i.amount) for i in target_insts], Decimal("0"))
    
    # Recovery Goal: 70% of total receivable
    recovery_goal = total_receivable * Decimal("0.70")
    
    # Actual Recovered: Those in range paid within the period
    recovered_insts = [i for i in target_insts if i.status == "PAGA" and i.paid_at and p_start <= i.paid_at.date() <= p_end]
    actual_recovered = sum([Decimal(i.amount) for i in recovered_insts], Decimal("0"))
    
    achieved_percent = (actual_recovered / recovery_goal * 100) if recovery_goal > 0 else Decimal("0")
    
    # Tiers: 100-109 (1%), 110-119 (2%), 120+ (3%)
    if achieved_percent >= 120: comm_p = Decimal("3.0")
    elif achieved_percent >= 110: comm_p = Decimal("2.0")
    elif achieved_percent >= 100: comm_p = Decimal("1.0")
    else: comm_p = Decimal("0.0")
    
    comm_value = actual_recovered * (comm_p / 100)
    
    return {
        "user_id": collector_id,
        "portfolio_range": portfolio_range,
        "period_start": p_start,
        "period_end": p_end,
        "total_receivable": total_receivable,
        "recovery_goal": recovery_goal,
        "actual_recovered": actual_recovered,
        "achieved_percent": achieved_percent,
        "commission_percent": comm_p,
        "commission_value": comm_value,
        "missing": max(Decimal("0"), recovery_goal - actual_recovered)
    }

# -----------------------------------------------------------------------------
# App
# -----------------------------------------------------------------------------
app = FastAPI(title="Gestor de Cobrança — Portal Móveis v4")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# --- APScheduler Setup ---
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.scheduler import run_collection_check

_scheduler = BackgroundScheduler()
_scheduler.add_job(
    run_collection_check,
    trigger=CronTrigger(hour=8, minute=0),
    args=[SessionLocal],
    id="daily_collection_check",
    replace_existing=True,
)

@app.on_event("startup")
def start_scheduler():
    _scheduler.start()

@app.on_event("shutdown")
def stop_scheduler():
    _scheduler.shutdown(wait=False)

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/version")
def version():
    return {"title": APP_TITLE, "version": APP_VERSION}

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            db.add(User(
                name="Admin Portal Móveis",
                email=DEFAULT_ADMIN_EMAIL,
                password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
                role="ADMIN",
                active=True
            ))
            db.commit()

        if db.query(CollectionRule).count() == 0:
            seeds = [
                (-3, -1, "LEVE", "WHATSAPP",
                 "Olá {nome}, lembrete amigável: sua parcela de {valor} vence em {vencimento}. — Portal Móveis",
                 0),
                (0, 4, "LEVE", "WHATSAPP",
                 "Olá {nome}, sua parcela de {valor} venceu dia {vencimento}. Já conseguiu pagar? — Portal Móveis",
                 1),
                (5, 14, "MODERADA", "WHATSAPP",
                 "Olá {nome}, constamos {qtd} parcela(s) em aberto totalizando {total}. Podemos agendar o pagamento para hoje? — Portal Móveis",
                 2),
                (15, 29, "MODERADA", "LIGACAO",
                 "Olá {nome}, seu débito de {total} está com {dias_atraso} dias de atraso. Precisamos regularizar para evitar bloqueio. — Portal Móveis",
                 3),
                (30, 59, "INTENSA", "LIGACAO",
                 "URGENTE: {nome}, seu contrato está na fase de cobrança intensa. Entre em contato urgente para acordo do valor {total}. — Portal Móveis",
                 4),
                (60, 9999, "INTENSA", "ACORDO",
                 "NOTIFICAÇÃO EXTRAJUDICIAL: {nome}, seu débito de {total} será encaminhado para protesto. Ligue agora para negociação. — Portal Móveis",
                 5),
            ]
            for s,e,l,a,m,p in seeds:
                db.add(CollectionRule(start_days=s, end_days=e, level=l, default_action=a, template_message=m, priority=p, active=True))
            db.commit()
    finally:
        db.close()

# -----------------------------------------------------------------------------
# Pages
# -----------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    try:
        require_login(request, db)
        return RedirectResponse("/dashboard", status_code=HTTP_302_FOUND)
    except HTTPException:
        return RedirectResponse("/login", status_code=HTTP_302_FOUND)

@app.get("/orders", response_class=HTMLResponse)
def orders_page(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    return render("dashboard.html", request=request, user=user, title="Pedidos / Vendas", 
                  total_open="R$ 0,00", total_overdue="R$ 0,00", total_upcoming="R$ 0,00", 
                  buckets={}, promises=[], today=today().isoformat())

@app.get("/finance", response_class=HTMLResponse)
def finance_page(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    return render("dashboard.html", request=request, user=user, title="Financeiro",
                  total_open="R$ 0,00", total_overdue="R$ 0,00", total_upcoming="R$ 0,00", 
                  buckets={}, promises=[], today=today().isoformat())

@app.get("/agreements", response_class=HTMLResponse)
def agreements_page(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    return render("dashboard.html", request=request, user=user, title="Acordos",
                  total_open="R$ 0,00", total_overdue="R$ 0,00", total_upcoming="R$ 0,00", 
                  buckets={}, promises=[], today=today().isoformat())

@app.get("/reports", response_class=HTMLResponse)
def reports_page(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    return render("dashboard.html", request=request, user=user, title="Relatórios",
                  total_open="R$ 0,00", total_overdue="R$ 0,00", total_upcoming="R$ 0,00", 
                  buckets={}, promises=[], today=today().isoformat())

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return render("login.html", request=request, user=None, title="Login", error=None)

@app.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.active or not verify_password(password, user.password_hash):
        return render("login.html", request=request, user=None, title="Login", error="Email ou senha inválidos.")
    request.session["uid"] = user.id
    return RedirectResponse("/dashboard", status_code=HTTP_302_FOUND)

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=HTTP_302_FOUND)

@app.get("/api/fila/prioridade")
def api_fila_prioridade(request: Request, limit: int = 20, db: Session = Depends(get_db)):
    user = require_login(request, db)
    
    # Base query for open installments
    q = db.query(Installment).join(Customer).filter(Installment.status == "ABERTA")
    
    # Filter by store if collector
    if user.role == "COBRANCA" and user.store:
        q = q.filter(Customer.store == user.store)
    
    insts = q.all()
    
    # Group by customer
    customer_data = {}
    for i in insts:
        cid = i.customer_id
        delay = days_overdue(i.due_date)
        if delay <= 0: continue
        
        if cid not in customer_data:
            last_action = db.query(CollectionAction).filter(CollectionAction.customer_id == cid).order_by(CollectionAction.created_at.desc()).first()
            customer_data[cid] = {
                "cliente_id": cid,
                "nome_cliente": i.customer.name,
                "phone": i.customer.whatsapp or "",
                "valor_em_aberto": 0,
                "max_atraso": 0,
                "data_vencimento": i.due_date,
                "ultimo_contato": last_action.created_at if last_action else None,
                "ultimo_contato_str": last_action.created_at.strftime("%d/%m/%Y") if last_action else "Sem contato"
            }
        
        customer_data[cid]["valor_em_aberto"] += float(i.open_amount)
        if delay > customer_data[cid]["max_atraso"]:
            customer_data[cid]["max_atraso"] = delay
            customer_data[cid]["data_vencimento"] = i.due_date

    fila = list(customer_data.values())
    
    def sort_key(item):
        contact_ts = item["ultimo_contato"].timestamp() if item["ultimo_contato"] else 0
        return (-item["max_atraso"], -item["valor_em_aberto"], contact_ts)

    fila.sort(key=sort_key)
    result = fila[:limit]
    
    for item in result:
        days = item["max_atraso"]
        if days > 60: label = "Crítico (>60d)"
        elif days > 30: label = "Alerta (30d+)"
        else: label = f"{days} dias atraso"
        item["status_label"] = label
        if item["ultimo_contato"]:
            item["ultimo_contato"] = item["ultimo_contato"].isoformat()
        item["data_vencimento"] = item["data_vencimento"].isoformat()

    return result

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)

    q = db.query(Installment).join(Customer).filter(Installment.status == "ABERTA")
    if user.role == "COBRANCA" and user.store:
        q = q.filter(Customer.store == user.store)

    insts = q.all()
    total_open = sum([Decimal(i.open_amount) for i in insts], Decimal("0"))
    
    # Simple recovery rate calculation (Paid / (Paid + Open)) logic requires history.
    # For now, let's just count Paid installs in the last 30 days vs Open
    paid_last_30 = db.query(Installment).filter(Installment.status == "PAGA", Installment.paid_at >= datetime.utcnow() - timedelta(days=30)).all()
    total_paid_30 = sum([Decimal(i.amount) for i in paid_last_30], Decimal("0"))
    
    if (total_paid_30 + total_open) > 0:
        recovery_rate = (total_paid_30 / (total_paid_30 + total_open)) * 100
    else:
        recovery_rate = Decimal(0)

    overdue = [i for i in insts if days_overdue(i.due_date) > 0 and Decimal(i.open_amount) > 0]
    total_overdue = sum([Decimal(i.open_amount) for i in overdue], Decimal("0"))
    
    # "Vence Hoje" calculation (strictly today)
    due_today_insts = [i for i in insts if days_overdue(i.due_date) == 0 and Decimal(i.open_amount) > 0]
    due_today_total = sum([Decimal(i.open_amount) for i in due_today_insts], Decimal("0"))
    
    # "Próximos 7 dias" calculation
    upcoming = [i for i in insts if -7 <= days_overdue(i.due_date) < 0 and Decimal(i.open_amount) > 0]
    total_upcoming = sum([Decimal(i.open_amount) for i in upcoming], Decimal("0"))

    buckets = {"0-4":0,"5-14":0,"15-29":0,"30-59":0,"60+":0}
    for i in overdue:
        d = days_overdue(i.due_date)
        if 1 <= d <= 4: buckets["0-4"] += 1
        elif 5 <= d <= 14: buckets["5-14"] += 1
        elif 15 <= d <= 29: buckets["15-29"] += 1
        elif 30 <= d <= 59: buckets["30-59"] += 1
        else: buckets["60+"] += 1

    promises = db.query(CollectionAction).filter(CollectionAction.promised_date == today()).order_by(CollectionAction.created_at.desc()).limit(10).all()

    # Calculate current commission for the card (Collectors only)
    current_commission = "R$ 0,00"
    if user.role == "COBRANCA":
        comm_data = calculate_collector_commission(db, user.id, "30", today().year, today().month)
        current_commission = format_money(comm_data["commission_value"])

    # Diagnostics (Admin)
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
                  due_today_total=due_today_total, # Raw decimal for brl filter
                  buckets=buckets, promises=promises, today=today().isoformat(),
                  recovery_rate=recovery_rate,
                  current_commission=current_commission,
                  admin_stats=admin_stats)

# -----------------------------------------------------------------------------
# Customers list + search + assign
# -----------------------------------------------------------------------------
@app.get("/customers", response_class=HTMLResponse)
def customers_page(request: Request, q: str = "", store: str = "", db: Session = Depends(get_db)):
    user = require_login(request, db)
    query = db.query(Customer)
    if user.role == "COBRANCA" and user.store:
        query = query.filter(Customer.store == user.store)
    if store:
        query = query.filter(Customer.store == store)

    if q.strip():
        s = f"%{q.strip()}%"
        query = query.filter(Customer.name.ilike(s))

    customers = query.order_by(Customer.name.asc()).limit(300).all()

    # compute summary (open total + max overdue)
    rows = []
    for c in customers:
        insts = [i for i in c.installments if i.status == "ABERTA" and Decimal(i.open_amount) > 0]
        if insts:
            max_over = max(days_overdue(i.due_date) for i in insts)
            total_open = sum(Decimal(i.open_amount) for i in insts)
        else:
            max_over, total_open = 0, Decimal("0")
        rows.append({"c": c, "max_over": max_over, "total_open": total_open, "prio": bucket_priority(max_over)})

    # users for assign (admin only)
    users = db.query(User).filter(User.active == True).order_by(User.name.asc()).all() if user.role == "ADMIN" else []
    return render("customers.html", request=request, user=user, title="Clientes",
                  rows=rows, q=q, store=store, stores=stores_list(db), users=users)

@app.post("/customers/{customer_id}/assign")
def assign_customer(request: Request, customer_id: int, assigned_to_user_id: int = Form(...), db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas ADMIN")
    c = db.get(Customer, customer_id)
    if not c:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    if assigned_to_user_id == 0:
        c.assigned_to_user_id = None
    else:
        u = db.get(User, assigned_to_user_id)
        if not u:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        c.assigned_to_user_id = u.id
    db.commit()
    return RedirectResponse("/customers", status_code=HTTP_302_FOUND)

# -----------------------------------------------------------------------------
# Import
# -----------------------------------------------------------------------------
@app.get("/import", response_class=HTMLResponse)
def import_page(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas ADMIN")
    return render("import.html", request=request, user=user, title="Importação")

def read_csv_upload(file: UploadFile) -> List[Dict[str, str]]:
    content = file.file.read()
    try:
        text = content.decode("utf-8-sig")
    except Exception:
        text = content.decode("latin-1")
    f = io.StringIO(text)
    return [dict(r) for r in csv.DictReader(f)]

@app.post("/import/customers")
def import_customers(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas ADMIN")

    rows = read_csv_upload(file)
    errors = 0
    upserts = 0
    for r in rows:
        ext = (r.get("cliente_id") or "").strip()
        name = (r.get("nome") or "").strip()
        if not ext or not name:
            errors += 1
            continue
        cust = db.query(Customer).filter(Customer.external_key == ext).first()
        if not cust:
            cust = Customer(external_key=ext, name=name)
            db.add(cust)
        cust.name = name
        cust.cpf_cnpj = (r.get("cpf_cnpj") or "").strip() or None
        cust.whatsapp = (r.get("telefone_whatsapp") or "").strip() or None
        cust.store = (r.get("loja") or "").strip() or None
        cust.address = (r.get("endereco") or "").strip() or None
        upserts += 1
    db.commit()
    return RedirectResponse(f"/import?msg=Clientes importados: {upserts}. Erros: {errors}.", status_code=HTTP_302_FOUND)

@app.post("/import/installments")
def import_installments(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas ADMIN")

    rows = read_csv_upload(file)
    errors = 0
    upserts = 0
    for r in rows:
        ext = (r.get("cliente_id") or "").strip()
        cust = db.query(Customer).filter(Customer.external_key == ext).first()
        if not cust:
            errors += 1
            continue
        try:
            contract_id = (r.get("contrato_id") or "").strip()
            inst_no = int((r.get("parcela_numero") or "1").strip())
            due = parse_date(r.get("vencimento") or "")
            amount = parse_decimal(r.get("valor_parcela") or "0")
            open_amount = parse_decimal(r.get("valor_em_aberto") or "0")
            status = (r.get("status") or "ABERTA").strip().upper()
        except Exception:
            errors += 1
            continue

        inst = db.query(Installment).filter(
            Installment.customer_id == cust.id,
            Installment.contract_id == contract_id,
            Installment.installment_number == inst_no,
            Installment.due_date == due
        ).first()
        if not inst:
            inst = Installment(
                customer_id=cust.id,
                contract_id=contract_id,
                installment_number=inst_no,
                due_date=due,
                amount=amount,
                open_amount=open_amount,
                status=status
            )
            db.add(inst)
        else:
            inst.amount = amount
            inst.open_amount = open_amount
            inst.status = status
        upserts += 1

    db.commit()
    return RedirectResponse(f"/import?msg=Parcelas importadas: {upserts}. Erros: {errors}.", status_code=HTTP_302_FOUND)

# -----------------------------------------------------------------------------
# Queue (respects store and assigned_to when cobranca)
# -----------------------------------------------------------------------------
@app.get("/queue", response_class=HTMLResponse)
def queue_page(request: Request, 
               store: Optional[str] = None, 
               range: Optional[str] = None, 
               tab: Optional[str] = None,
               db: Session = Depends(get_db)):
    user = require_login(request, db)

    # Base query for customers
    query = db.query(Customer)
    if user.role == "COBRANCA":
        if user.store:
            query = query.filter(Customer.store == user.store)
        # Restriction by assignment if any assignments exist
        assigned_exist = db.query(Customer).filter(Customer.assigned_to_user_id != None).count() > 0
        if assigned_exist:
            query = query.filter(Customer.assigned_to_user_id == user.id)

    if store:
        query = query.filter(Customer.store == store)

    customers = query.all()

    items = []
    for c in customers:
        # filter installments: always open and > 0
        insts = [i for i in c.installments if i.status == "ABERTA" and Decimal(i.open_amount) > 0]
        
        # Apply strict tab filtering if requested
        if tab == "due_today":
            insts = [i for i in insts if days_overdue(i.due_date) == 0]
        elif tab == "overdue":
            insts = [i for i in insts if days_overdue(i.due_date) > 0]
        
        if not insts:
            continue
            
        max_over = max([days_overdue(i.due_date) for i in insts])
        total_open = sum([Decimal(i.open_amount) for i in insts], Decimal("0"))
        pr = bucket_priority(max_over)
        items.append({
            "customer": c, 
            "max_overdue": max_over, 
            "priority": pr, 
            "total_open": total_open, 
            "count_open": len(insts)
        })

    # Legacy Range Filtering (Dashboard buckets)
    if range:
        def ok(d):
            if range == "0-4": return 1 <= d <= 4
            if range == "5-14": return 5 <= d <= 14
            if range == "15-29": return 15 <= d <= 29
            if range == "30-59": return 30 <= d <= 59
            if range == "60+": return d >= 60
            if range == "a-vencer": return d < 0
            return True
        items = [it for it in items if ok(it["max_overdue"])]

    # Sorting: Prio, Overdue, Amount
    items.sort(key=lambda it: (it["priority"], it["max_overdue"], it["total_open"]), reverse=True)

    return render("queue.html", request=request, user=user, title="Fila de Cobrança", 
                  items=items[:500],
                  stores=stores_list(db), 
                  selected_store=store or "", 
                  selected_range=range or "",
                  tab=tab)

# -----------------------------------------------------------------------------
# Customer detail + actions
# -----------------------------------------------------------------------------
@app.get("/customers/{customer_id}", response_class=HTMLResponse)
def customer_page(request: Request, customer_id: int, db: Session = Depends(get_db)):
    user = require_login(request, db)
    c = db.get(Customer, customer_id)
    if not c:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    # Permission: cobranca sees only own store/assigned if set
    if user.role == "COBRANCA":
        if user.store and (c.store or "").upper() != user.store.upper():
            raise HTTPException(status_code=403, detail="Sem acesso (loja)")
        assigned_exist = db.query(Customer).filter(Customer.assigned_to_user_id != None).count() > 0
        if assigned_exist and c.assigned_to_user_id != user.id:
            raise HTTPException(status_code=403, detail="Sem acesso (carteira)")

    open_insts = [i for i in c.installments if i.status == "ABERTA" and Decimal(i.open_amount) > 0]
    max_over = max([days_overdue(i.due_date) for i in open_insts], default=0)
    total_open = sum([Decimal(i.open_amount) for i in open_insts], Decimal("0"))

    rule = rule_for_overdue(db, max_over)
    template = rule.template_message if rule else "Olá {nome}. Vamos regularizar? — Portal Móveis"
    level = rule.level if rule else "LEVE"

    next_due = min([i.due_date for i in open_insts], default=None)
    # Support both case keys for templates
    replacements = {
        "{nome}": c.name, "{NOME}": c.name,
        "{data}": (next_due.strftime("%d/%m/%Y") if next_due else ""), "{DATA}": (next_due.strftime("%d/%m/%Y") if next_due else ""),
        "{vencimento}": (next_due.strftime("%d/%m/%Y") if next_due else ""),
        "{valor}": (format_money(open_insts[0].open_amount) if open_insts else ""), "{VALOR}": (format_money(open_insts[0].open_amount) if open_insts else ""),
        "{qtd}": str(len(open_insts)), "{QTD}": str(len(open_insts)),
        "{total}": format_money(total_open), "{TOTAL}": format_money(total_open),
        "{dias}": str(max_over), "{DIAS}": str(max_over),
        "{dias_atraso}": str(max_over),
    }
    
    msg = template
    for k, v in replacements.items():
        msg = msg.replace(k, v)
    link = wa_link(c.whatsapp, msg)

    actions = db.query(CollectionAction).filter(CollectionAction.customer_id == c.id).order_by(CollectionAction.created_at.desc()).limit(80).all()
    installments = sorted(c.installments, key=lambda i: (i.status != "ABERTA", i.due_date))

    # add computed overdue per installment
    inst_view = []
    for i in installments:
        od = days_overdue(i.due_date) if i.status == "ABERTA" and Decimal(i.open_amount) > 0 else 0
        inst_view.append({"i": i, "overdue": od})

    # Compute totals for the detailed parcels table footer
    _today = today()
    total_vencido = sum(
        [Decimal(i.open_amount) for i in c.installments
         if i.status == "ABERTA" and Decimal(i.open_amount) > 0 and i.due_date < _today],
        Decimal("0"),
    )
    total_titulo = sum([Decimal(i.amount) for i in c.installments], Decimal("0"))
    total_quitado = sum(
        [Decimal(i.amount) - Decimal(i.open_amount) for i in c.installments
         if Decimal(i.open_amount) < Decimal(i.amount)],
        Decimal("0"),
    )

    return render("customer.html", request=request, user=user, title="Cliente", customer=c,
                  installments=inst_view, actions=actions,
                  total_open=format_money(total_open), max_overdue=max_over,
                  wa_link=link, wa_message=msg, rule_level=level,
                  total_vencido=format_money(total_vencido),
                  total_titulo=format_money(total_titulo),
                  total_quitado=format_money(total_quitado))

@app.post("/actions")
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
    c = db.get(Customer, customer_id)
    if not c:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    pd = None
    if promised_date.strip():
        try:
            pd = parse_date(promised_date.strip())
        except Exception:
            pd = None
    pa = None
    if promised_amount.strip():
        try:
            pa = parse_decimal(promised_amount.strip())
        except Exception:
            pa = None

    db.add(CollectionAction(
        customer_id=c.id,
        user_id=user.id,
        action_type=action_type.strip().upper(),
        outcome=outcome.strip(),
        notes=notes.strip() or None,
        promised_date=pd,
        promised_amount=pa
    ))
    db.commit()
    return RedirectResponse(f"/customers/{c.id}", status_code=HTTP_302_FOUND)

# -----------------------------------------------------------------------------
# Rules (admin)
# -----------------------------------------------------------------------------
@app.get("/rules", response_class=HTMLResponse)
def rules_page(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas ADMIN")
    rules = db.query(CollectionRule).order_by(CollectionRule.priority.desc(), CollectionRule.start_days.asc()).all()
    return render("rules.html", request=request, user=user, title="Régua", rules=rules, msg=request.query_params.get("msg"))

@app.post("/rules/{rule_id}/toggle")
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

@app.post("/rules")
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

# -----------------------------------------------------------------------------
# Messages (report + manual trigger)
# -----------------------------------------------------------------------------
@app.get("/messages", response_class=HTMLResponse)
def messages_page(
    request: Request,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
):
    user = require_login(request, db)

    query = db.query(SentMessage).join(Customer)

    if status:
        query = query.filter(SentMessage.status == status.upper())
    if date_from:
        try:
            df = parse_date(date_from)
            query = query.filter(SentMessage.created_at >= datetime(df.year, df.month, df.day))
        except ValueError:
            pass
    if date_to:
        try:
            dt = parse_date(date_to)
            query = query.filter(SentMessage.created_at < datetime(dt.year, dt.month, dt.day) + timedelta(days=1))
        except ValueError:
            pass
    if q:
        query = query.filter(Customer.name.ilike(f"%{q}%"))

    messages = query.order_by(SentMessage.created_at.desc()).limit(200).all()

    # Stats
    _today = today()
    _start = datetime(_today.year, _today.month, _today.day)
    _end = _start + timedelta(days=1)
    total_today = db.query(SentMessage).filter(SentMessage.created_at >= _start, SentMessage.created_at < _end).count()
    total_simulated = db.query(SentMessage).filter(SentMessage.status == "SIMULADO").count()
    total_pending = db.query(SentMessage).filter(SentMessage.status == "PENDENTE").count()
    total_sent = db.query(SentMessage).filter(SentMessage.status == "ENVIADO").count()

    return render("messages.html", request=request, user=user, title="Mensagens",
                  messages=messages,
                  total_today=total_today,
                  total_simulated=total_simulated,
                  total_pending=total_pending,
                  total_sent=total_sent,
                  selected_status=status or "",
                  selected_date_from=date_from or "",
                  selected_date_to=date_to or "",
                  selected_q=q or "")


@app.post("/messages/run-now")
def messages_run_now(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas ADMIN")
    stats = run_collection_check(SessionLocal)
    msg = f"Execução concluída! Verificados: {stats['checked']}, Criadas: {stats['created']}, Puladas (freq): {stats['skipped_freq']}, Sem telefone: {stats['skipped_no_phone']}"
    return RedirectResponse(f"/messages?msg={msg}", status_code=HTTP_302_FOUND)

# -----------------------------------------------------------------------------
# Commissions
# -----------------------------------------------------------------------------
@app.get("/commissions", response_class=HTMLResponse)
def commissions_page(request: Request, month: int = None, year: int = None, range: str = "30", db: Session = Depends(get_db)):
    user = require_login(request, db)
    
    # Defaults
    if not month: month = today().month
    if not year: year = today().year
    
    # If not admin, force his own user_id
    # (Actually the generate logic needs to run, for now we just show what's in DB or empty)
    # The user asked for "Generate" to recalculate live.
    
    results = []
    # If admin, show all collectors
    if user.role == "ADMIN":
        collectors = db.query(User).filter(User.role == "COBRANCA").all()
        for c in collectors:
            res = calculate_collector_commission(db, c.id, range, year, month)
            res["name"] = c.name
            res["store"] = c.store
            results.append(res)
    else:
        # Just himself
        res = calculate_collector_commission(db, user.id, range, year, month)
        res["name"] = user.name
        res["store"] = user.store
        results.append(res)
        
    return render("commissions.html", request=request, user=user, title="Comissão", 
                  results=results, year=year, month=month, range=range,
                  msg=request.query_params.get("msg"))

@app.post("/commissions/generate")
def commissions_generate(request: Request, db: Session = Depends(get_db)):
    # In this MVP, generate is just a refresh because the `commissions_page` calculates live
    return RedirectResponse("/commissions?msg=Recalculado com sucesso!", status_code=HTTP_302_FOUND)

@app.post("/commissions/save")
def commissions_save(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas ADMIN")
        
    # Save snapshots of current calculations
    # For now, let's just save one for each collector for the current month
    month = today().month
    year = today().year
    range_val = "30"
    
    collectors = db.query(User).filter(User.role == "COBRANCA").all()
    for c in collectors:
        res = calculate_collector_commission(db, c.id, range_val, year, month)
        
        # Check if already exists for this period
        existing = db.query(ComissaoCobranca).filter(
            ComissaoCobranca.user_id == c.id,
            ComissaoCobranca.period_start == res["period_start"],
            ComissaoCobranca.portfolio_range == range_val
        ).first()
        
        if existing:
            # Update
            existing.total_receivable = res["total_receivable"]
            existing.recovery_goal = res["recovery_goal"]
            existing.actual_recovered = res["actual_recovered"]
            existing.achieved_percent = res["achieved_percent"]
            existing.commission_percent = res["commission_percent"]
            existing.commission_value = res["commission_value"]
        else:
            db.add(ComissaoCobranca(
                period_start=res["period_start"],
                period_end=res["period_end"],
                user_id=c.id,
                store=c.store,
                portfolio_range=range_val,
                total_receivable=res["total_receivable"],
                recovery_goal=res["recovery_goal"],
                actual_recovered=res["actual_recovered"],
                achieved_percent=res["achieved_percent"],
                commission_percent=res["commission_percent"],
                commission_value=res["commission_value"]
            ))
            
    db.commit()
    return RedirectResponse("/commissions?msg=Fechamento salvo com sucesso!", status_code=HTTP_302_FOUND)

# -----------------------------------------------------------------------------
# Users (admin)
# -----------------------------------------------------------------------------
@app.get("/users", response_class=HTMLResponse)
def users_page(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas ADMIN")
    users = db.query(User).order_by(User.role.desc(), User.name.asc()).all()
    return render("users.html", request=request, user=user, title="Usuários", users=users, msg=request.query_params.get("msg"))

@app.post("/users")
def users_create(request: Request,
                 name: str = Form(...),
                 email: str = Form(...),
                 password: str = Form(...),
                 role: str = Form(...),
                 store: str = Form(""),
                 db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas ADMIN")
    if db.query(User).filter(User.email == email.strip()).first():
        return RedirectResponse("/users?msg=Email já existe.", status_code=HTTP_302_FOUND)
    db.add(User(
        name=name.strip(),
        email=email.strip(),
        password_hash=hash_password(password.strip()),
        role=role.strip().upper(),
        store=(store.strip() or None),
        active=True
    ))
    db.commit()
    return RedirectResponse("/users?msg=Usuário criado.", status_code=HTTP_302_FOUND)

@app.post("/users/{user_id}/toggle")
def users_toggle(request: Request, user_id: int, db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas ADMIN")
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    u.active = not u.active
    db.commit()
    return RedirectResponse("/users?msg=Usuário atualizado.", status_code=HTTP_302_FOUND)

# -----------------------------------------------------------------------------
# Import Routes
# -----------------------------------------------------------------------------
from app.services.import_xlsx import process_excel_import

@app.post("/import/upload")
async def import_upload_file(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    user = require_login(request, db)
    
    if not file.filename.endswith(".xlsx"):
        return RedirectResponse("/import?msg=Erro: Apenas arquivos Excel (.xlsx) são permitidos&type=error", status_code=303)

    content = await file.read()
    result = process_excel_import(content, db, user.id)

    if result.get("error"):
        return RedirectResponse(f"/import?msg={result['error']}&type=error", status_code=303)

    msg = f"Importação concluída! {result['customers']} clientes e {result['installments']} parcelas."
    if result.get("errors"):
        msg += f" (Ocorreram {len(result['errors'])} erros)"
    
    return RedirectResponse(f"/import?msg={msg}&type=success", status_code=303)


@app.get("/import")
async def import_page(request: Request):
    user = require_login(request, get_db()) # simplified auth check
    return templates.TemplateResponse("import.html", {"request": request, "user": user, "title": "Importar Planilha"})
