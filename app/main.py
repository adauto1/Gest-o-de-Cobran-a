
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
    ForeignKey, Numeric, Text, Index, func, case, desc, literal_column
)
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, Session, joinedload, subqueryload

from passlib.context import CryptContext
from jinja2 import Environment, FileSystemLoader, select_autoescape
from bs4 import BeautifulSoup

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
APP_VERSION = "4.0"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# Services
from app.services.sync_customers import sync_erp_customers
from app.services.whatsapp import enviar_whatsapp, verificar_conexao, ZAPI_BASE_URL


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
    email = Column(String(120), nullable=True)
    notes = Column(Text, nullable=True)
    profile_cobranca = Column(String(20), nullable=False, default="AUTOMATICO")
    assigned_to_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    assigned_to = relationship("User")
    installments = relationship("Installment", back_populates="customer", cascade="all, delete-orphan")
    actions = relationship("CollectionAction", back_populates="customer", cascade="all, delete-orphan")

    __table_args__ = (
        Index('ix_customers_name', 'name'),
        Index('ix_customers_store', 'store'),
        Index('ix_customers_assigned_to', 'assigned_to_user_id'),
    )

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


class Configuracoes(Base):
    __tablename__ = "configuracoes"
    id = Column(Integer, primary_key=True)
    whatsapp_ativo = Column(Boolean, default=False)
    whatsapp_modo_teste = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow)

class WhatsappHistorico(Base):
    __tablename__ = "whatsapp_historico"
    id = Column(Integer, primary_key=True)
    cliente_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    telefone = Column(String(20), nullable=True)
    mensagem = Column(Text, nullable=True)
    tipo = Column(String(50), nullable=True)  # 'regua_automatica', 'manual', 'lembrete'
    status = Column(String(20), nullable=True) # 'enviado', 'simulado', 'erro'
    resposta = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    
    cliente = relationship("Customer")


class MessageDispatchLog(Base):
    __tablename__ = "message_dispatch_log"
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    scheduled_for = Column(Date, nullable=True) # quando deveria enviar
    executed_at = Column(DateTime, default=datetime.utcnow)
    mode = Column(String(20)) # TEST/PROD
    status = Column(String(20)) # SIMULATED, SENT, FAILED, RESCHEDULED, SKIPPED
    regua = Column(String(20)) # LEVE, MODERADA, INTENSA
    gatilho_dias = Column(Integer)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    customer_name = Column(String(190))
    destination_phone = Column(String(40))
    cpf_mask = Column(String(20))
    
    # Detalhes financeiros snapshot
    data_vencimento = Column(Date, nullable=True)
    valor_original = Column(Numeric(10, 2), nullable=True)
    valor_atualizado = Column(Numeric(10, 2), nullable=True)
    total_divida = Column(Numeric(10, 2), nullable=True)
    qtd_parcelas_atrasadas = Column(Integer, nullable=True)
    
    compliance_block_reason = Column(String(50), nullable=True) # DOMINGO | FERIADO_NACIONAL | FORA_HORARIO_COMERCIAL | OK
    message_rendered = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True) # JSON string
    
    customer = relationship("Customer")

    __table_args__ = (
        Index('ix_mdl_scheduled', 'scheduled_for'),
        Index('ix_mdl_status_created', 'status', 'created_at'),
        Index('ix_mdl_customer_created', 'customer_id', 'created_at'),
        Index('ix_mdl_regua_gatilho', 'regua', 'gatilho_dias', 'created_at'),
    )

# Helpers moved up for model usage
def today() -> date:
    return datetime.utcnow().date()

def days_overdue(due: date) -> int:
    return (today() - due).days

class Director(Base):
    __tablename__ = "directors"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    phone = Column(String(40), nullable=False) # WhatsApp format
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class DirectorAlertLog(Base):
    __tablename__ = "director_alert_logs"
    id = Column(Integer, primary_key=True)
    director_id = Column(Integer, ForeignKey("directors.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    alert_date = Column(Date, default=today)
    created_at = Column(DateTime, default=datetime.utcnow)

    director = relationship("Director")
    customer = relationship("Customer")


class FinancialUser(Base):
    __tablename__ = "financial_users"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    phone = Column(String(40), nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class FinancialAlertLog(Base):
    __tablename__ = "financial_alert_logs"
    id = Column(Integer, primary_key=True)
    financial_user_id = Column(Integer, ForeignKey("financial_users.id"), nullable=False)
    alert_date = Column(Date, default=today)
    item_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    financial_user = relationship("FinancialUser")




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

def parse_date(date_str: str) -> Optional[date]:
    if not date_str: return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except:
        return None

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
    "outbox.html": ("messages", "Outbox — Conferência"),
    "settings.html": ("settings", "Configurações"),
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


def bucket_priority(max_overdue: int) -> int:
    if max_overdue >= 90: return 5 # Crítica (Intensa)
    if max_overdue >= 30: return 4 # Alta (Moderada)
    if max_overdue >= 5:  return 2 # Média (Leve)
    return 1 # Normal (Lembrete)

def get_regua_nivel(customer_profile: str, max_overdue: int) -> str:
    if customer_profile and customer_profile != "AUTOMATICO":
        return customer_profile
    p = bucket_priority(max_overdue)
    if p >= 5: return "INTENSA"
    if p >= 3: return "MODERADA"
    return "LEVE"

def rule_for_overdue(db: Session, overdue_days: int, level: str = "LEVE") -> Optional[CollectionRule]:
    rules = db.query(CollectionRule).filter(
        CollectionRule.active == True,
        CollectionRule.level == level
    ).all()
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

@app.exception_handler(401)
async def unauthorized_handler(request: Request, exc: HTTPException):
    return RedirectResponse("/login", status_code=HTTP_302_FOUND)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Custom exception handler for 401/NotAuthenticated to redirect to login
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        # Check if it's a browser request (HTML) and not an API call
        accept = request.headers.get("accept", "")
        if "text/html" in accept and not request.url.path.startswith("/api/"):
            return RedirectResponse("/login", status_code=302)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
from fastapi.responses import JSONResponse

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

# --------------------------------------------------------------------------
# Auto-migration: adds missing columns to existing tables
# --------------------------------------------------------------------------
import logging as _logging
_migrate_log = _logging.getLogger("auto_migrate")

def _auto_migrate(eng):
    """Compare SQLAlchemy models with DB schema, add missing columns."""
    from sqlalchemy import inspect as sa_inspect, text
    inspector = sa_inspect(eng)
    for table in Base.metadata.sorted_tables:
        if table.name not in inspector.get_table_names():
            continue  # create_all already handles new tables
        existing = {c["name"] for c in inspector.get_columns(table.name)}
        for col in table.columns:
            if col.name not in existing:
                col_type = col.type.compile(eng.dialect)
                default = ""
                if col.default is not None:
                    dv = col.default.arg
                    if isinstance(dv, str):
                        default = f" DEFAULT '{dv}'"
                    elif dv is not None:
                        default = f" DEFAULT {dv}"
                nullable = "" if col.nullable else " NOT NULL"
                # SQLite can't add NOT NULL without default
                if nullable and not default:
                    nullable = ""
                sql = f"ALTER TABLE {table.name} ADD COLUMN {col.name} {col_type}{default}{nullable}"
                _migrate_log.info(f"Migrating: {sql}")
                with eng.begin() as conn:
                    conn.execute(text(sql))

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    _auto_migrate(engine)  # add missing columns to existing tables
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

        # Rehash admin password with current algorithm (argon2)
        admin = db.query(User).filter(User.email == DEFAULT_ADMIN_EMAIL).first()
        if admin and not admin.password_hash.startswith("$argon2"):
            admin.password_hash = hash_password(DEFAULT_ADMIN_PASSWORD)
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
    return render("login.html", request=request, user=None, title="Login", error=None, now=datetime.utcnow)

@app.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.active or not verify_password(password, user.password_hash):
        return render("login.html", request=request, user=None, title="Login", error="Email ou senha inválidos.", now=datetime.utcnow)
    request.session["uid"] = user.id
    return RedirectResponse("/dashboard", status_code=HTTP_302_FOUND)

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=HTTP_302_FOUND)

@app.get("/api/fila/prioridade")
def api_fila_prioridade(request: Request, page: int = 1, limit: int = 30, db: Session = Depends(get_db)):
    user = require_login(request, db)
    
    # Page must be at least 1
    if page < 1: page = 1
    
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
                "profile_cobranca": i.customer.profile_cobranca or "AUTOMATICO",
                "ultimo_contato": last_action.created_at if last_action else None,
                "ultimo_contato_str": last_action.created_at.strftime("%d/%m/%Y") if last_action else "Sem contato",
                "qtd_parcelas": 0
            }
        
        customer_data[cid]["qtd_parcelas"] += 1
        customer_data[cid]["valor_em_aberto"] += float(i.open_amount)
        if delay > customer_data[cid]["max_atraso"]:
            customer_data[cid]["max_atraso"] = delay
            customer_data[cid]["data_vencimento"] = i.due_date

    fila = list(customer_data.values())
    
    def sort_key(item):
        contact_ts = item["ultimo_contato"].timestamp() if item["ultimo_contato"] else 0
        return (-item["max_atraso"], -item["valor_em_aberto"], contact_ts)

    fila.sort(key=sort_key)
    
    total_items = len(fila)
    total_pages = (total_items + limit - 1) // limit
    
    start = (page - 1) * limit
    end = start + limit
    result_items = fila[start:end]
    
    for item in result_items:
        days = item["max_atraso"]
        # Unificando lógica de status com a regra 30/90 para visualização
        if days >= 90: label = "Crítico (90+ d)"
        elif days >= 30: label = "Moderado (30+ d)"
        else: label = f"{days} dias"
        item["status_label"] = label
        
        # Calcular nível da régua para o indicador visual
        item["regua_nivel"] = get_regua_nivel(item["profile_cobranca"], days)

        if item["ultimo_contato"]:
            item["ultimo_contato"] = item["ultimo_contato"].isoformat()
        item["data_vencimento"] = item["data_vencimento"].isoformat()

    return {
        "items": result_items,
        "total_items": total_items,
        "total_pages": total_pages,
        "current_page": page
    }


def calculate_recovery_goals(db: Session, user: User):
    today_dt = datetime.utcnow().date()
    start_of_month = datetime(today_dt.year, today_dt.month, 1)

    # Paid this month
    q_paid = db.query(Installment).filter(Installment.status == "PAGA", Installment.paid_at >= start_of_month)
    if user.role == "COBRANCA" and user.store:
         q_paid = q_paid.join(Customer).filter(Customer.store == user.store)
    paid_installs = q_paid.all()

    # Open (currently overdue)
    q_open = db.query(Installment).filter(Installment.status == "ABERTA")
    if user.role == "COBRANCA" and user.store:
         q_open = q_open.join(Customer).filter(Customer.store == user.store)
    open_installs = q_open.all()

    dataset = {
        "30": {"paid": Decimal(0), "total": Decimal(0)}, # 1-30 days
        "60": {"paid": Decimal(0), "total": Decimal(0)}, # 31-60 days
        "90": {"paid": Decimal(0), "total": Decimal(0)}, # 61-90 days
    }

    def get_bucket(d):
        if 1 <= d <= 30: return "30"
        if 31 <= d <= 60: return "60"
        if 61 <= d <= 90: return "90"
        return None

    # Sum Paid (based on delay at payment)
    for i in paid_installs:
        if i.due_date and i.paid_at:
            delay = (i.paid_at.date() - i.due_date).days
            k = get_bucket(delay)
            if k:
                dataset[k]["paid"] += i.amount
                dataset[k]["total"] += i.amount # It was part of the bucket

    # Sum Open (currently overdue)
    for i in open_installs:
        if i.due_date:
            delay = (today_dt - i.due_date).days
            k = get_bucket(delay)
            if k:
                dataset[k]["total"] += i.open_amount

    # Build results
    results = []
    target_pct = Decimal("0.70")
    for k in ["30", "60", "90"]:
        d = dataset[k]
        goal = d["total"] * target_pct
        actual = d["paid"]
        missing = goal - actual
        
        # Formatting
        results.append({
            "label": f"{k} DIAS",
            "goal_fmt": format_money(goal),
            "actual_fmt": format_money(actual),
            "missing_fmt": format_money(missing) if missing > 0 else "R$ 0,00", # Or negative? Screenshot shows "-R$ 351". User said "quds falta".
            "missing_val": missing,
            "is_reached": missing <= 0
        })
    return results

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

    # Calculate fiado meta (percentage of portfolio overdue)
    fiado_percentage = Decimal(0)
    if total_open > 0:
        fiado_percentage = (total_overdue / total_open) * 100
    
    # "Vence Hoje" calculation (strictly today)
    due_today_insts = [i for i in insts if days_overdue(i.due_date) == 0 and Decimal(i.open_amount) > 0]
    due_today_total = sum([Decimal(i.open_amount) for i in due_today_insts], Decimal("0"))
    
    # "Próximos 7 dias" calculation
    upcoming = [i for i in insts if -7 <= days_overdue(i.due_date) < 0 and Decimal(i.open_amount) > 0]
    total_upcoming = sum([Decimal(i.open_amount) for i in upcoming], Decimal("0"))

    # Aging buckets matching mockup design
    aging = {
        "1_30":  {"count": 0, "value": Decimal("0")},
        "31_60": {"count": 0, "value": Decimal("0")},
        "61_90": {"count": 0, "value": Decimal("0")},
        "90_plus": {"count": 0, "value": Decimal("0")},
    }
    urgent_count = 0  # >60 days without recent contact
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

    # Format aging values for template
    for k in aging:
        aging[k]["value_fmt"] = format_money(aging[k]["value"])

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
                  due_today_total=due_today_total,
                  aging=aging, urgent_count=urgent_count,
                  promises=promises, today=today().isoformat(),
                  recovery_rate=recovery_rate,
                  fiado_percentage=fiado_percentage,
                  recovery_goals=calculate_recovery_goals(db, user),
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

    # Eager load for performance
    query = query.options(
        subqueryload(Customer.installments),
        joinedload(Customer.assigned_to)
    )

    customers = query.order_by(Customer.name.asc()).limit(300).all()

    # compute summary (open total + max overdue)
    rows = []
    
    # Pre-fetch last contacts if possible or do inside loop (optimize later if slow)
    # For 300 items, doing single queries is okay-ish to avoid complexity, but bulk is better.
    # We will do simple query inside for now to match logic.

    for c in customers:
        insts = [i for i in c.installments if i.status == "ABERTA" and Decimal(i.open_amount) > 0]
        if insts:
            max_over = max(days_overdue(i.due_date) for i in insts)
            total_open = sum(Decimal(i.open_amount) for i in insts)
            count_open = len(insts)
        else:
            max_over, total_open, count_open = 0, Decimal("0"), 0
        
        # Last contact
        last = db.query(CollectionAction).filter(CollectionAction.customer_id == c.id).order_by(CollectionAction.created_at.desc()).first()
        ultimo_contato_str = last.created_at.strftime("%d/%m/%Y") if last else "Sem contato"

        regua_nivel = get_regua_nivel(c.profile_cobranca, max_over)
        
        # Status Label Logic (same as queue)
        if max_over > 60: status_label = "Crítico (>60d)"
        elif max_over > 30: status_label = "Alerta (30d+)"
        elif max_over > 0: status_label = f"{max_over} dias atraso"
        else: status_label = "Em dia"

        rows.append({
            "c": c, 
            "max_over": max_over, 
            "total_open": total_open, 
            "count_open": count_open,
            "prio": bucket_priority(max_over), 
            "regua_nivel": regua_nivel,
            "ultimo_contato_str": ultimo_contato_str,
            "status_label": status_label
        })

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

@app.post("/customers/{customer_id}/change-profile")
def change_profile(request: Request, customer_id: int, profile: str = Form(...), db: Session = Depends(get_db)):
    user = require_login(request, db)
    # Allow ADMIN and COBRANCA
    if user.role not in ["ADMIN", "COBRANCA"]:
        raise HTTPException(status_code=403, detail="Sem permissão")
    
    c = db.get(Customer, customer_id)
    if not c:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    
    # Valida input
    valid_profiles = ["AUTOMATICO", "LEVE", "MODERADA", "INTENSA"]
    if profile not in valid_profiles:
        raise HTTPException(status_code=400, detail="Perfil inválido")

    c.profile_cobranca = profile
    db.commit()
    
    referer = request.headers.get("referer")
    if referer:
        return RedirectResponse(referer, status_code=HTTP_302_FOUND)
    return RedirectResponse(f"/customers/{customer_id}", status_code=HTTP_302_FOUND)

@app.patch("/api/customers/{customer_id}/regua")
def alterar_regua(customer_id: int, dados: dict, db: Session = Depends(get_db)):
    cliente = db.query(Customer).filter(Customer.id == customer_id).first()
    if not cliente:
        return {"success": False, "message": "Cliente não encontrado"}
    
    nova_regua = dados.get("profile_cobranca")
    if nova_regua not in ["AUTOMATICO", "LEVE", "MODERADA", "INTENSA"]:
        return {"success": False, "message": "Régua inválida"}
    
    cliente.profile_cobranca = nova_regua
    db.commit()
    return {"success": True, "message": "Régua alterada com sucesso"}

@app.patch("/api/customers/{customer_id}")
def update_customer(customer_id: int, dados: dict, request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    cliente = db.get(Customer, customer_id)
    if not cliente:
        return {"success": False, "message": "Cliente não encontrado"}
    
    # Permission check (similar to customer detail page)
    if user.role == "COBRANCA":
        if user.store and (cliente.store or "").upper() != user.store.upper():
            return {"success": False, "message": "Sem permissão (loja)"}

    # Update allowed fields
    if "whatsapp" in dados:
        cliente.whatsapp = str(dados["whatsapp"]).strip()
    if "address" in dados:
        cliente.address = str(dados["address"]).strip()
    
    cliente.updated_at = datetime.utcnow()
    db.commit()
    return {"success": True, "message": "Cliente atualizado com sucesso"}

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

def parse_infocommerce_html(content: bytes) -> List[Dict]:
    """Parse HTML do InfoCommerce extraindo títulos por posicionamento CSS."""
    try:
        text = content.decode('latin-1', errors='ignore')
    except:
        text = content.decode('utf-8', errors='ignore')
    
    soup = BeautifulSoup(text, 'lxml')
    tags = soup.find_all(['div', 'p', 'span'])
    
    # Agrupa elementos por linha (coordenada top)
    rows_data = {}
    for tag in tags:
        style = tag.get('style', '')
        top_match = re.search(r'top:(\d+)px', style)
        left_match = re.search(r'left:(\d+)px', style)
        txt = tag.get_text().strip()
        
        if top_match and left_match and txt:
            top = int(top_match.group(1))
            left = int(left_match.group(1))
            if top not in rows_data:
                rows_data[top] = {}
            rows_data[top][left] = txt
    
    # Extrai dados das linhas
    parsed = []
    for top in sorted(rows_data.keys()):
        row = rows_data[top]
        emissao = row.get(54)
        cliente = row.get(264)
        vencimento = row.get(588)
        valor_raw = row.get(648)
        
        # Valida se é uma linha de título (tem datas válidas)
        if emissao and vencimento:
            if re.match(r'\d{2}/\d{2}/\d{4}', emissao) and re.match(r'\d{2}/\d{2}/\d{4}', vencimento):
                if valor_raw:
                    try:
                        # Converte valor (formato brasileiro: 1.234,56 -> 1234.56)
                        v_str = valor_raw.replace('.', '').replace(',', '.')
                        valor = float(v_str)
                        parsed.append({
                            'vencimento': vencimento,
                            'cliente': (cliente or "DESCONHECIDO").strip().upper(),
                            'valor': valor
                        })
                    except:
                        continue
    
    return parsed

@app.post("/import/upload")
def import_erp_upload(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Importa dados do ERP a partir de arquivo HTML (InfoCommerce) ou Excel."""
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas ADMIN")
    
    content = file.file.read()
    filename = file.filename.lower()
    
    # Detecta tipo de arquivo
    if filename.endswith(('.html', '.htm')):
        # Parse HTML do InfoCommerce
        parsed_data = parse_infocommerce_html(content)
        
        if not parsed_data:
            return RedirectResponse("/import?msg=Erro: Nenhum dado encontrado no arquivo HTML.", status_code=HTTP_302_FOUND)
        
        # PASSO 1: Snapshot das parcelas ABERTAS antes da importação
        open_installments = db.query(Installment).filter(
            Installment.status == "ABERTA"
        ).all()
        
        existing_keys = {
            (inst.customer_id, inst.due_date, inst.amount)
            for inst in open_installments
        }
        
        # PASSO 2: Importa dados (modo incremental - upsert)
        customers_cache = {}
        count_customers = 0
        count_installments = 0
        errors = 0
        new_keys = set()
        
        for item in parsed_data:
            try:
                # Cliente (usa nome como external_key)
                cliente_name = item['cliente']
                if cliente_name not in customers_cache:
                    cust = db.query(Customer).filter(Customer.external_key == cliente_name).first()
                    if not cust:
                        cust = Customer(
                            external_key=cliente_name,
                            name=cliente_name,
                            whatsapp="",
                            store="LOJA 1"
                        )
                        db.add(cust)
                        db.flush()
                        count_customers += 1
                    customers_cache[cliente_name] = cust.id
                
                # Parcela
                due_date = datetime.strptime(item['vencimento'], '%d/%m/%Y').date()
                valor = Decimal(str(item['valor']))
                
                # Adiciona ao conjunto de chaves do novo relatório
                new_keys.add((customers_cache[cliente_name], due_date, valor))
                
                # Verifica se já existe (por cliente + data de vencimento + valor)
                inst = db.query(Installment).filter(
                    Installment.customer_id == customers_cache[cliente_name],
                    Installment.due_date == due_date,
                    Installment.amount == valor
                ).first()
                
                if not inst:
                    # Cria nova parcela
                    inst = Installment(
                        customer_id=customers_cache[cliente_name],
                        contract_id=f"ERP-{cliente_name[:10]}-{due_date.strftime('%Y%m%d')}",
                        installment_number=1,
                        due_date=due_date,
                        amount=valor,
                        open_amount=valor,
                        status="ABERTA"
                    )
                    db.add(inst)
                    count_installments += 1
                else:
                    # Atualiza parcela existente
                    inst.open_amount = valor
                    inst.status = "ABERTA"
                    count_installments += 1
                
            except Exception as e:
                errors += 1
                continue
        
        # PASSO 3: Detecta parcelas que sumiram (foram quitadas)
        paid_keys = existing_keys - new_keys
        count_paid = 0
        
        for customer_id, due_date, amount in paid_keys:
            inst = db.query(Installment).filter(
                Installment.customer_id == customer_id,
                Installment.due_date == due_date,
                Installment.amount == amount,
                Installment.status == "ABERTA"
            ).first()
            
            if inst:
                inst.status = "PAGA"
                inst.paid_at = datetime.now()
                inst.open_amount = Decimal("0")
                count_paid += 1
        
        db.commit()
        
        msg = f"Importação concluída! Clientes: {count_customers} novos. Parcelas: {count_installments}. Baixadas: {count_paid}. Erros: {errors}."
        return RedirectResponse(f"/import?msg={msg}", status_code=HTTP_302_FOUND)
    
    elif filename.endswith(('.xlsx', '.xls')):
        # TODO: Implementar parse de Excel
        return RedirectResponse("/import?msg=Erro: Importação de Excel ainda não implementada. Use HTML do InfoCommerce.", status_code=HTTP_302_FOUND)
    
    else:
        return RedirectResponse("/import?msg=Erro: Formato de arquivo não suportado. Use .html ou .xlsx", status_code=HTTP_302_FOUND)

@app.post("/import/reset")
def reset_database(request: Request, db: Session = Depends(get_db)):
    """Zera todos os dados do app (apenas ADMIN). CUIDADO: Ação irreversível!"""
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas ADMIN")
    
    try:
        # Deleta todas as ações de cobrança
        db.query(CollectionAction).delete()
        
        # Deleta todas as mensagens enviadas
        db.query(SentMessage).delete()
        
        # Deleta todas as comissões
        db.query(ComissaoCobranca).delete()
        
        # Deleta todas as parcelas
        deleted_installments = db.query(Installment).delete()
        
        # Deleta todos os clientes
        deleted_customers = db.query(Customer).delete()
        
        db.commit()
        
        msg = f"App zerado com sucesso! Removidos: {deleted_customers} clientes e {deleted_installments} parcelas."
        return RedirectResponse(f"/import?msg={msg}", status_code=HTTP_302_FOUND)
    
    except Exception as e:
        db.rollback()
        return RedirectResponse(f"/import?msg=Erro ao zerar app: {str(e)}", status_code=HTTP_302_FOUND)

# -----------------------------------------------------------------------------
# Queue (respects store and assigned_to when cobranca)
# -----------------------------------------------------------------------------
@app.get("/queue", response_class=HTMLResponse)
def queue_page(request: Request, 
               store: Optional[str] = None, 
               range: Optional[str] = None, # Legacy
               filtro_atraso: Optional[str] = None, # New
               tab: Optional[str] = None,
               page: int = 1, # Pagination
               db: Session = Depends(get_db)):
    user = require_login(request, db)
    
    # Defaults
    page_size = 20
    if page < 1: page = 1
    offset = (page - 1) * page_size

    # --- SQL APPROACH FOR PERFORMANCE AND PAGINATION ---
    # We need to calculate max_overdue and total_open per customer, filter by store/user,
    # order by priority, and then paginate. Doing this in Python with 21k customers is too slow.

    # 1. Base query on Installments (status='ABERTA')
    # Use SQLite's julianday for date diff: (julianday('now') - julianday(due_date))
    # We group by customer_id to get aggregated metrics.
    
    # Base Filters
    filters = [
        Installment.status == "ABERTA",
        Installment.open_amount > 0
    ]

    # Special logic for "Due Today" (shows ONLY today's titles)
    days_diff_expr = func.julianday(func.date('now')) - func.julianday(Installment.due_date)
    
    if tab == "due_today":
        filters.append(days_diff_expr == 0)
    
    stmt = db.query(
        Installment.customer_id,
        func.max(days_diff_expr).label("max_overdue_days"),
        func.sum(Installment.open_amount).label("total_open_val"),
        func.count(Installment.id).label("count_open_val")
    ).filter(*filters)

    # 2. Filter buckets (tabs) IN SQL
    # "overdue" -> overdue > 0
    # For "due_today", the WHERE clause already filtered it, so we don't need HAVING,
    # but we can keep logic if we want to be safe or reuse stmt.
    
    if tab == "overdue":
        stmt = stmt.having(func.max(days_diff_expr) > 0)
    
    stmt = stmt.group_by(Installment.customer_id).subquery()

    # 3. Main Query: Join Customer with Aggregated Subquery
    query = db.query(Customer, stmt.c.max_overdue_days, stmt.c.total_open_val, stmt.c.count_open_val)\
        .join(stmt, Customer.id == stmt.c.customer_id)

    # 3.5 Apply Drill-down Filter (filtro_atraso)
    filtro_label = None
    if filtro_atraso:
        if filtro_atraso == "1-30":
            query = query.filter(stmt.c.max_overdue_days >= 1, stmt.c.max_overdue_days <= 30)
            filtro_label = "1-30 dias de atraso"
        elif filtro_atraso == "31-60":
            query = query.filter(stmt.c.max_overdue_days >= 31, stmt.c.max_overdue_days <= 60)
            filtro_label = "31-60 dias de atraso"
        elif filtro_atraso == "61-90":
            query = query.filter(stmt.c.max_overdue_days >= 61, stmt.c.max_overdue_days <= 90)
            filtro_label = "61-90 dias de atraso"
        elif filtro_atraso == "90-plus":
            query = query.filter(stmt.c.max_overdue_days > 90)
            filtro_label = "+90 dias de atraso"

    # 4. Filters (Store/User)
    if user.role == "COBRANCA":
        if user.store:
            query = query.filter(Customer.store == user.store)
        # Assigned Check
        assigned_exist = db.query(Customer).filter(Customer.assigned_to_user_id != None).count() > 0
        if assigned_exist:
            query = query.filter(Customer.assigned_to_user_id == user.id)
    
    if store:
        query = query.filter(Customer.store == store)


    # 5. Sorting Priority Logic (SQL Case)
    # Priority 3: >= 30 days (Alta)
    # Priority 2: >= 5 days (Média)
    # Priority 1: < 5 days (Normal - includes 0 and negative/future)
    prio_case = case(
        (stmt.c.max_overdue_days >= 30, 3),
        (stmt.c.max_overdue_days >= 5, 2),
        else_=1
    )

    # 6. Order By + Pagination
    # Orders: Priority DESC, Max Overdue DESC, Total Open DESC
    query = query.order_by(
        prio_case.desc(),
        stmt.c.max_overdue_days.desc(),
        stmt.c.total_open_val.desc()
    )

    # Count total for pagination
    total_items = query.count()
    total_pages = (total_items + page_size - 1) // page_size

    # Fetch Page
    results = query.offset(offset).limit(page_size).all()

    # 7. Convert to display format
    items = []
    for row in results:
        cust, mo, to, co = row
        max_over = int(mo) if mo else 0
        items.append({
            "customer": cust,
            "max_overdue": max_over,
            "priority": bucket_priority(max_over),
            "total_open": Decimal(to) if to else Decimal(0),
            "count_open": co,
            "regua_nivel": get_regua_nivel(cust.profile_cobranca, max_over),
            # Pre-calculate labels for template
            "status_label": "Crítico (>60d)" if max_over > 60 else ("Alerta (30d+)" if max_over > 30 else f"{max_over} dias atraso"),
            "ultimo_contato": None, # Loading these per page is fast enough now (20 items) or use subquery
            "data_vencimento": (today() - timedelta(days=max_over)).isoformat()
        })
    
    # Load last contact securely for just these 20 items
    for item in items:
        cid = item["customer"].id
        last = db.query(CollectionAction).filter(CollectionAction.customer_id == cid).order_by(CollectionAction.created_at.desc()).first()
        if last:
            item["ultimo_contato"] = last.created_at.isoformat()
            item["ultimo_contato_str"] = last.created_at.strftime("%d/%m/%Y")
        else:
             item["ultimo_contato_str"] = "Sem contato"

    return render("queue.html", request=request, user=user, title="Fila de Cobrança", 
                  items=items,
                  stores=stores_list(db), 
                  selected_store=store or "", 
                  selected_range=range or "",
                  tab=tab,
                  page=page,
                  total_pages=total_pages,
                  filtro_ativo=filtro_label)

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

    # Escalonamento inteligente (Unificado: Tempo de atraso)
    c_profile = getattr(c, "profile_cobranca", "AUTOMATICO")
    effective_profile = c_profile
    if c_profile == "AUTOMATICO":
        if max_over >= 90: effective_profile = "INTENSA"
        elif max_over >= 30: effective_profile = "MODERADA"
        else: effective_profile = "LEVE"

    rule = rule_for_overdue(db, max_over, level=effective_profile)
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
                  regua_nivel=get_regua_nivel(c.profile_cobranca, max_over),
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
@app.get("/outbox")
def outbox_page(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    return render("outbox.html", request=request, user=user)

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

    messages_list = []
    for m in messages:
        # Get max overdue for this customer to calculate current regua_nivel
        insts = [i for i in m.customer.installments if i.status == "ABERTA" and i.open_amount > 0]
        max_over = max([days_overdue(i.due_date) for i in insts], default=0)
        regua = get_regua_nivel(m.customer.profile_cobranca, max_over)
        messages_list.append({"m": m, "regua_nivel": regua})

    return render("messages.html", request=request, user=user, title="Mensagens",
                  messages=messages_list,
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
    msg = f"Execução concluída! Verificados: {stats['checked']}, Criadas/Enviadas: {stats['created']}, Reagendadas: {stats['rescheduled']}, Puladas (freq): {stats['skipped_freq']}, Sem telefone: {stats['skipped_no_phone']}"
    referer = request.headers.get("referer", "/outbox")
    return RedirectResponse(f"{referer}{'&' if '?' in referer else '?'}msg={msg}", status_code=HTTP_302_FOUND)

@app.get("/api/mensagens/outbox")
def api_get_outbox(
    request: Request,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    regua: Optional[str] = None,
    cliente: Optional[str] = None,
    only_test: bool = False,
    only_rescheduled: bool = False,
    page: int = 1,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    user = require_login(request, db)
    
    query = db.query(MessageDispatchLog)
    
    # Filtros
    if date_from:
        try:
            dt = parse_date(date_from)
            query = query.filter(MessageDispatchLog.created_at >= datetime(dt.year, dt.month, dt.day))
        except: pass
        
    if date_to:
        try:
            dt = parse_date(date_to)
            query = query.filter(MessageDispatchLog.created_at < datetime(dt.year, dt.month, dt.day) + timedelta(days=1))
        except: pass
        
    if status:
        stat_list = status.split(",")
        query = query.filter(MessageDispatchLog.status.in_(stat_list))
        
    if regua:
        query = query.filter(MessageDispatchLog.regua == regua)
        
    if cliente:
        query = query.filter(
            (MessageDispatchLog.customer_name.ilike(f"%{cliente}%")) |
            (MessageDispatchLog.destination_phone.ilike(f"%{cliente}%")) |
            (MessageDispatchLog.cpf_mask.ilike(f"%{cliente}%"))
        )
        
    if only_test:
        query = query.filter(MessageDispatchLog.mode == "TEST")
        
    if only_rescheduled:
        query = query.filter(MessageDispatchLog.status == "RESCHEDULED")
        
    # KPIs (snapshot based on current filters or global for period? Usually based on period/filters)
    # Vamos calcular KPIs baseados na query atual (sem paginação)
    # Mas fazer count(*) multiplos pode ser pesado. Vamos fazer um group by status.
    
    # Clone query for stats
    # stats_query = query.with_entities(MessageDispatchLog.status, func.count(MessageDispatchLog.id)).group_by(MessageDispatchLog.status)
    # stats_res = stats_query.all()
    # stats_map = {s: c for s, c in stats_res}
    
    total_items = query.count()
    total_simulated = query.filter(MessageDispatchLog.status == "SIMULADO").count()
    total_rescheduled = query.filter(MessageDispatchLog.status == "RESCHEDULED").count()
    total_sent = query.filter(MessageDispatchLog.status == "ENVIADO").count()
    total_failed = query.filter(MessageDispatchLog.status == "FAILED").count()
    
    # Paginação
    logs = query.order_by(MessageDispatchLog.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    
    results = []
    for l in logs:
        results.append({
            "id": l.id,
            "created_at": l.created_at.isoformat(),
            "scheduled_for": l.scheduled_for.isoformat() if l.scheduled_for else None,
            "mode": l.mode,
            "status": l.status,
            "regua": l.regua,
            "gatilho": l.gatilho_dias,
            "regua_display": f"{l.regua} (D{'+' if l.gatilho_dias >=0 else ''}{l.gatilho_dias})",
            "cliente_nome": l.customer_name,
            "cliente_id": l.customer_id,
            "telefone": l.destination_phone,
            "valor": float(l.total_divida) if l.total_divida else 0.00, # ou valor_original
            "compliance_reason": l.compliance_block_reason,
            "error": l.error_message,
            "metadata": l.metadata_json # Passar string json direto ou parsear? Front pode parsear.
        })
        
    return {
        "data": results,
        "meta": {
            "page": page,
            "limit": limit,
            "total": total_items
        },
        "kpis": {
            "total": total_items, # Na visualização atual
            "simulated": total_simulated,
            "rescheduled": total_rescheduled,
            "sent": total_sent,
            "failed": total_failed
        }
    }


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
from app.services.import_html import process_html_import

@app.post("/import/upload")
async def import_upload_file(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    user = require_login(request, db)
    
    if file.filename.lower().endswith((".html", ".htm")):
         content = await file.read()
         result = process_html_import(content, db, user.id)
    elif file.filename.lower().endswith((".xlsx", ".xls")):
         content = await file.read()
         result = process_excel_import(content, db, user.id)
    else:
        return RedirectResponse("/import?msg=Erro: Apenas arquivos Excel (.xlsx) ou HTML (.html) são permitidos&type=error", status_code=303)

    if result.get("error"):
        return RedirectResponse(f"/import?msg={result['error']}&type=error", status_code=303)

    msg = f"Importação concluída! {result['customers']} clientes e {result['installments']} parcelas."
    if result.get("errors"):
        msg += f" (Ocorreram {len(result['errors'])} erros)"
    
    return RedirectResponse(f"/import?msg={msg}&type=success", status_code=303)

# -----------------------------------------------------------------------------
# API Routes for Dashboard Modals
# -----------------------------------------------------------------------------
@app.get("/api/customers/{customer_id}")
def get_customer_api(customer_id: int, request: Request, db: Session = Depends(get_db)):
    """Busca dados do cliente para edição."""
    user = require_login(request, db)
    cust = db.query(Customer).filter(Customer.id == customer_id).first()
    if not cust:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    
    # Verifica permissão (COBRANCA só vê seus clientes)
    if user.role == "COBRANCA":
        if user.store and cust.store != user.store:
            raise HTTPException(status_code=403, detail="Sem permissão")
        assigned_exist = db.query(Customer).filter(Customer.assigned_to_user_id != None).count() > 0
        if assigned_exist and cust.assigned_to_user_id != user.id:
            raise HTTPException(status_code=403, detail="Sem permissão")
    
    return {
        "id": cust.id,
        "name": cust.name,
        "whatsapp": cust.whatsapp or "",
        "address": cust.address or "",
        "email": cust.email or "",
        "notes": cust.notes or "",
        "profile_cobranca": cust.profile_cobranca or "AUTOMATICO"
    }

@app.patch("/api/customers/{customer_id}")
def update_customer_api(
    customer_id: int,
    data: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    """Atualiza dados do cliente."""
    user = require_login(request, db)
    cust = db.query(Customer).filter(Customer.id == customer_id).first()
    if not cust:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    
    # Verifica permissão
    if user.role == "COBRANCA":
        if user.store and cust.store != user.store:
            raise HTTPException(status_code=403, detail="Sem permissão")
        assigned_exist = db.query(Customer).filter(Customer.assigned_to_user_id != None).count() > 0
        if assigned_exist and cust.assigned_to_user_id != user.id:
            raise HTTPException(status_code=403, detail="Sem permissão")
    
    # Atualiza campos
    if "whatsapp" in data:
        cust.whatsapp = data["whatsapp"].strip() if data["whatsapp"] else None
    if "address" in data:
        cust.address = data["address"].strip() if data["address"] else None
    if "email" in data:
        cust.email = data["email"].strip() if data["email"] else None
    if "notes" in data:
        cust.notes = data["notes"].strip() if data["notes"] else None
    if "profile_cobranca" in data:
        cust.profile_cobranca = data["profile_cobranca"].strip().upper()
    
    db.commit()
    return {"success": True}

@app.post("/api/collection-actions")
def create_collection_action_api(
    data: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    """Registra ação de cobrança."""
    user = require_login(request, db)
    
    # Valida customer_id
    customer_id = data.get("customer_id")
    if not customer_id:
        raise HTTPException(status_code=400, detail="customer_id obrigatório")
    
    cust = db.query(Customer).filter(Customer.id == customer_id).first()
    if not cust:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    
    # Verifica permissão
    if user.role == "COBRANCA":
        if user.store and cust.store != user.store:
            raise HTTPException(status_code=403, detail="Sem permissão")
        assigned_exist = db.query(Customer).filter(Customer.assigned_to_user_id != None).count() > 0
        if assigned_exist and cust.assigned_to_user_id != user.id:
            raise HTTPException(status_code=403, detail="Sem permissão")
    
    # Cria ação
    promised_date = None
    if data.get("promised_date"):
        try:
            promised_date = datetime.strptime(data["promised_date"], "%Y-%m-%d").date()
        except:
            pass
    
    action = CollectionAction(
        customer_id=customer_id,
        user_id=user.id,
        action_type=data.get("action_type", "LIGACAO"),
        outcome=data.get("outcome", ""),
        notes=data.get("notes", ""),
        promised_date=promised_date
    )
    db.add(action)
    db.commit()
    
    return {"success": True, "id": action.id}


@app.get("/import")
async def import_page(request: Request):
    user = require_login(request, get_db()) # simplified auth check
    return templates.TemplateResponse("import.html", {"request": request, "user": user, "title": "Importar Planilha"})

@app.post("/api/sync/customers")
def api_sync_customers(request: Request, db: Session = Depends(get_db)):
    """Sincroniza todos os clientes do ERP InfoCommerce."""
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas administradores podem sincronizar o cadastro completo.")
    
    file_path = r"C:\Users\Adauto Pereira\Desktop\DADOS ERP\RelatorioDECLIENTE InfoCommerce.HTM"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"Arquivo não encontrado em: {file_path}")
    
    result = sync_erp_customers(file_path, db)
    return result

# --- WhatsApp Integration ---

@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    config = db.query(Configuracoes).first()
    if not config:
        config = Configuracoes(whatsapp_ativo=False, whatsapp_modo_teste=True)
        db.add(config)
        db.commit()
        db.refresh(config)
    
    return render("settings.html", request=request, user=user, title="Configurações", config=config)

@app.post("/settings")
async def update_settings(
    request: Request,
    db: Session = Depends(get_db)
):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    form = await request.form()
    whatsapp_ativo = form.get("whatsapp_ativo") == "on"
    whatsapp_modo_teste = form.get("whatsapp_modo_teste") == "on"
    
    config = db.query(Configuracoes).first()
    if not config:
        config = Configuracoes()
        db.add(config)
    
    config.whatsapp_ativo = whatsapp_ativo
    config.whatsapp_modo_teste = whatsapp_modo_teste
    config.updated_at = datetime.utcnow()
    db.commit()
    
    return RedirectResponse(url="/settings", status_code=303)

@app.post("/api/whatsapp/enviar-manual/{cliente_id}")
def enviar_whatsapp_manual(cliente_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    log_path = os.path.join(os.path.dirname(__file__), "debug_wa.log")
    
    def log_debug(msg):
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")

    log_debug(f"--- INÍCIO DISPARO MANUAL (Cliente ID: {cliente_id}) ---")
    
    # Fetch config
    config = db.query(Configuracoes).first()
    is_test = config.whatsapp_modo_teste if config else True
    log_debug(f"Modo Teste: {is_test}")

    cliente = db.query(Customer).filter(Customer.id == cliente_id).first()
    if not cliente:
        log_debug("ERRO: Cliente não encontrado")
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    if not cliente.whatsapp:
         log_debug("ERRO: Cliente sem WhatsApp")
         return {"success": False, "erro": "Cliente sem WhatsApp cadastrado"}

    # Buscar parcelas diretamente no banco
    all_insts = db.query(Installment).filter(
        Installment.customer_id == cliente_id,
        Installment.status.in_(["VENCIDA", "EM ABERTO", "ABERTA"])
    ).all()
    
    insts = sorted(all_insts, key=lambda x: x.due_date)
    log_debug(f"Parcelas encontradas: {len(insts)}")
    
    if not insts:
        log_debug("Fallback: Nenhuma parcela em aberto.")
        mensagem = f"Olá {cliente.name}!\n\nAqui é a Portal Móveis. Identificamos pendências em seu nome.\n\nEntre em contato conosco para regularizar sua situação.\n\n📍 Portal Móveis - Tacuru/MS"
    else:
        # Calcular dados do atraso
        total_open = sum(i.open_amount for i in insts)
        max_overdue = days_overdue(insts[0].due_date)
        nearest_due = insts[0].due_date
        log_debug(f"Dias de atraso: {max_overdue} | Vencimento: {nearest_due} | Total: {total_open}")
        
        # overdue_count: parcelas que já passaram do vencimento
        _today = date.today()
        overdue_count = len([i for i in insts if i.due_date < _today])
        
        # Identificar regra (Unificado com scheduler - Perfil Inteligente 30/90)
        c_profile = getattr(cliente, "profile_cobranca", "AUTOMATICO")
        effective_profile = c_profile
        if c_profile == "AUTOMATICO":
            if max_overdue >= 90: effective_profile = "INTENSA"
            elif max_overdue >= 30: effective_profile = "MODERADA"
            else: effective_profile = "LEVE"
            
        matched_rule = rule_for_overdue(db, max_overdue, level=effective_profile)
        
        if not matched_rule:
            log_debug(f"Fallback: Nenhuma regra para {max_overdue} dias.")
            mensagem = f"Olá {cliente.name}!\n\nAqui é a Portal Móveis. Identificamos pendências em seu nome.\n\nEntre em contato conosco para regularizar sua situação.\n\n📍 Portal Móveis - Tacuru/MS"
        else:
            log_debug(f"Regra Selecionada: ID {matched_rule.id} (Nível: {matched_rule.level})")
            
            # Preparar variáveis (mesma lógica do scheduler.py)
            msg_body = matched_rule.template_message
            cpf_raw = cliente.cpf_cnpj or ""
            cpf_masked = f"***.{cpf_raw[3:6]}.{cpf_raw[6:9]}-**" if len(cpf_raw) >= 11 else cpf_raw
            chave_pix = "00.000.000/0001-00" 
            link_pagto = f"https://portalmoveis.com.br/pagar/{cliente.external_key}"
            
            juros = Decimal("1.10") if max_overdue > 30 else Decimal("1.02")
            valor_com_juros = insts[0].open_amount * juros
            
            replacements = {
                "{nome}": cliente.name, "{NOME}": cliente.name,
                "{valor}": format_money(insts[0].open_amount),
                "{VALOR}": format_money(insts[0].open_amount),
                "{valor_com_juros}": format_money(valor_com_juros),
                "{total}": format_money(total_open), "{TOTAL}": format_money(total_open),
                "{total_divida}": format_money(total_open),
                "{dias_atraso}": str(max_overdue), "{DIAS}": str(max_overdue),
                "{dias}": str(max_overdue),
                "{vencimento}": nearest_due.strftime("%d/%m/%Y"),
                "{data_vencimento}": nearest_due.strftime("%d/%m/%Y"),
                "{data}": nearest_due.strftime("%d/%m/%Y"),
                "{DATA}": nearest_due.strftime("%d/%m/%Y"),
                "{qtd}": str(len(insts)), "{QTD}": str(len(insts)),
                "{quantidade_parcelas}": str(overdue_count),
                "{cpf}": cpf_masked,
                "{cpf_mascarado}": cpf_masked,
                "{telefone}": "(67) 99916-1881",
                "{chave_pix}": chave_pix,
                "{link_pagamento}": link_pagto,
            }
            for k, v in replacements.items():
                msg_body = msg_body.replace(k, v)
            
            mensagem = msg_body
            log_debug(f"Mensagem gerada: {mensagem[:50]}...")

    resultado = enviar_whatsapp(
        telefone=cliente.whatsapp,
        mensagem=mensagem,
        modo_teste=is_test
    )
    
    # Historico com Telemetria (no banco também)
    debug_data = {
        "insts": len(insts),
        "days": max_overdue if insts else None,
        "rule": matched_rule.id if 'matched_rule' in locals() and matched_rule else None,
        "mode": "TEST" if is_test else "PROD"
    }
    
    hist = WhatsappHistorico(
        cliente_id=cliente.id,
        telefone=cliente.whatsapp,
        mensagem=mensagem,
        tipo="manual",
        status=resultado.get("modo", "").lower(),
        resposta=str(debug_data)
    )
    db.add(hist)
    db.commit()
    log_debug("--- FIM DISPARO MANUAL ---")
    
    return resultado

@app.get("/api/whatsapp/status")
def verificar_status_zapi():
    return verificar_conexao()

# -----------------------------------------------------------------------------
# Directors API
# -----------------------------------------------------------------------------
@app.get("/api/directors")
def get_directors(request: Request, db: Session = Depends(get_db)):
    require_login(request, db)
    directors = db.query(Director).order_by(Director.name).all()
    return [{
        "id": d.id,
        "name": d.name,
    } for d in directors]

# -----------------------------------------------------------------------------
# Financial Users API
# -----------------------------------------------------------------------------
@app.get("/api/financial_users")
def get_financial_users(request: Request, db: Session = Depends(get_db)):
    require_login(request, db)
    users = db.query(FinancialUser).filter(FinancialUser.active == True).order_by(FinancialUser.name).all()
    return [{
        "id": u.id,
        "name": u.name,
        "phone": u.phone,
        "active": u.active
    } for u in users]

@app.post("/api/financial_users")
async def add_financial_user(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    form = await request.form()
    name = form.get("name")
    phone = form.get("phone")
    
    if not phone:
         raise HTTPException(status_code=400, detail="Telefone obrigatório")
         
    phone_clean = "".join([c for c in phone if c.isdigit()])
    if len(phone_clean) < 10:
        raise HTTPException(status_code=400, detail="Telefone inválido")

    fu = FinancialUser(name=name, phone=phone_clean, active=True)
    db.add(fu)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Erro ao salvar")
        
    return {"success": True, "id": fu.id}

@app.delete("/api/financial_users/{user_id}")
def delete_financial_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    require_login(request, db)
    fu = db.query(FinancialUser).filter(FinancialUser.id == user_id).first()
    if not fu:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    # Soft delete ou hard delete? Hard delete por enquanto
    db.delete(fu)
    db.commit()
    return {"success": True}

# -----------------------------------------------------------------------------
# Financial Reports API
# -----------------------------------------------------------------------------
@app.get("/api/financeiro/logs")
def get_financial_logs(request: Request, db: Session = Depends(get_db)):
    require_login(request, db)
    logs = db.query(FinancialAlertLog).order_by(FinancialAlertLog.created_at.desc()).limit(50).all()
    return [{
        "id": l.id,
        "user_name": l.financial_user.name if l.financial_user else "N/A",
        "date": l.alert_date.isoformat(),
        "created_at": l.created_at.isoformat(),
        "item_count": l.item_count
    } for l in logs]

@app.post("/api/financeiro/run-now")
async def run_financial_now(request: Request, db: Session = Depends(get_db)):
    require_login(request, db)
    result = await process_financial_notifications(db, force=True)
    return result

# -----------------------------------------------------------------------------

@app.post("/api/directors")
async def add_director(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    form = await request.form()
    name = form.get("name")
    phone = form.get("phone")
    
    # Validate phone basic
    if not phone:
         raise HTTPException(status_code=400, detail="Telefone obrigatório")
         
    phone_clean = "".join([c for c in phone if c.isdigit()])
    if len(phone_clean) < 10:
        raise HTTPException(status_code=400, detail="Telefone inválido")

    d = Director(name=name, phone=phone_clean, active=True)
    db.add(d)
    db.commit()
    db.refresh(d)
    return {"success": True, "id": d.id}

@app.delete("/api/directors/{director_id}")
def delete_director(director_id: int, request: Request, db: Session = Depends(get_db)):
    require_login(request, db)
    d = db.get(Director, director_id)
    if d:
        db.delete(d)
        db.commit()
    return {"success": True}

# -----------------------------------------------------------------------------
# Background Services - Director Notification
# -----------------------------------------------------------------------------
import asyncio

async def director_notification_loop():
    """
    Loop infinito que roda a cada 1 hora.
    Verifica clientes com >= 3 parcelas vencidas.
    Envia resumo para todos os diretores ativos.
    """
    while True:
        try:
            db = SessionLocal()
            # 1. Verificar se WhatsApp está ativo nas configurações
            config = db.query(Configuracoes).first()
            if not config or not config.whatsapp_ativo:
                print("[DirectorBot] WhatsApp inativo. Aguardando...")
            else:
                # 2. Buscar Diretores
                directors = db.query(Director).filter(Director.active == True).all()
                if not directors:
                    print("[DirectorBot] Nenhum diretor cadastrado.")
                else:
                    print(f"[DirectorBot] Iniciando verificação para {len(directors)} diretores...")
                    
                    # 3. Buscar clientes críticos (>= 3 parcelas vencidas)
                    # Otimização: Buscar IDs de clientes com installments vencidas
                    # SQL simples: contar parcelas abertas vencidas por cliente
                    # Atraso > 0 e Status = ABERTA
                    
                    # Subquery para contar parcelas vencidas
                    msg_buffer = [] # Lista de alertas para enviar
                    
                    # Iterar clientes 'problemáticos' (podemos otimizar com SQL Group By depois)
                    # Por enquanto, iteramos clientes com alguma parcela vencida
                    # Para performance, vamos fazer uma query agregada
                    
                    critical_stmt = db.query(
                        Installment.customer_id,
                        func.count(Installment.id).label("qtd_vencida"),
                        func.sum(Installment.open_amount).label("total_vencido"),
                        func.min(Installment.due_date).label("mais_antiga")
                    ).filter(
                        Installment.status == "ABERTA",
                        Installment.due_date < today()
                    ).group_by(Installment.customer_id).having(func.count(Installment.id) >= 3).all()
                    
                    for row in critical_stmt:
                        cid, qtd, total, old_date = row
                        
                        # Verificar se já enviamos alerta para este cliente nas últimas 24h para QUALQUER diretor
                        # Se JÁ enviamos hoje, não enviamos de novo para evitar spam flood
                        last_alert = db.query(DirectorAlertLog).filter(
                             DirectorAlertLog.customer_id == cid,
                             DirectorAlertLog.alert_date >= today()
                        ).first()
                        
                        if last_alert:
                            continue # Já alertado hoje
                            
                        # Montar mensagem
                        cust = db.get(Customer, cid)
                        dias_atraso = (today() - old_date).days
                        valor_fmt = format_money(total)
                        
                        msg = (
                            f"🚨 *ALERTA DE INADIMPLÊNCIA* 🚨\n\n"
                            f"Cliente: *{cust.name}*\n"
                            f"Parcelas Vencidas: {qtd}\n"
                            f"Valor Total: {valor_fmt}\n"
                            f"Maior Atraso: {dias_atraso} dias\n\n"
                            f"Acesse o sistema para verificar."
                        )
                        
                        # Enviar para TODOS os diretores
                        for direc in directors:
                            print(f"[DirectorBot] Enviando alerta de {cust.name} para {direc.name}...")
                            enviar_whatsapp(direc.phone, msg, modo_teste=config.whatsapp_modo_teste)
                            
                            # Logar envio
                            log = DirectorAlertLog(
                                director_id=direc.id,
                                customer_id=cid,
                                alert_date=today()
                            )
                            db.add(log)
                            
                        db.commit()
                        
                        # Pausa para não bloquear API do WhatsApp
                        await asyncio.sleep(2) 

            db.close()
        except Exception as e:
            print(f"[DirectorBot] Erro no loop: {e}")
        
        # Esperar 1 hora (3600 segundos)
        await asyncio.sleep(3600)

async def process_financial_notifications(db: Session, force: bool = False):
    """
    Processa as notificações financeiras (promessas de pagamento do dia).
    Se force=True, ignora a trava de envio único diário.
    """
    config = db.query(Configuracoes).first()
    if not config or not config.whatsapp_ativo:
        return {"success": False, "detail": "WhatsApp inativo"}

    fin_users = db.query(FinancialUser).filter(FinancialUser.active == True).all()
    if not fin_users:
        return {"success": False, "detail": "Nenhum usuário financeiro ativo"}

    target_date = today()
    promises = db.query(CollectionAction).filter(
        CollectionAction.promised_date == target_date,
        CollectionAction.outcome == "PROMESSA"
    ).all()

    if not promises:
        return {"success": True, "detail": "Nenhum agendamento para hoje", "sent_count": 0}

    # Montar mensagem
    total_val = sum([p.promised_amount or 0 for p in promises])
    msg_lines = [f"📅 *Agendamentos de Hoje ({target_date.strftime('%d/%m')})*"]
    
    for p in promises:
        c = db.get(Customer, p.customer_id)
        val = p.promised_amount or 0
        s_val = f"{val:,.2f}".replace(".", ",")
        msg_lines.append(f"• {c.name}: R$ {s_val}")
    
    s_total = f"{total_val:,.2f}".replace(".", ",")
    msg_lines.append(f"\n💰 *Total Previsto: R$ {s_total}*")
    
    full_msg = "\n".join(msg_lines)
    sent_count = 0

    for fu in fin_users:
        # Verificar se já recebeu hoje (se não for forçado)
        if not force:
            log = db.query(FinancialAlertLog).filter(
                FinancialAlertLog.financial_user_id == fu.id,
                FinancialAlertLog.alert_date == target_date
            ).first()
            if log:
                continue

        print(f"[FinancialBot] Enviando resumo para {fu.name}...")
        enviar_whatsapp(fu.phone, full_msg, modo_teste=config.whatsapp_modo_teste)
        
        # Logar envio
        new_log = FinancialAlertLog(
            financial_user_id=fu.id,
            alert_date=target_date,
            item_count=len(promises)
        )
        db.add(new_log)
        sent_count += 1
    
    db.commit()
    return {"success": True, "sent_count": sent_count, "items": len(promises)}

async def financial_notification_loop():
    print("[FinancialBot] Iniciando serviço de monitoramento de agendamentos...")
    while True:
        try:
            now = datetime.now()
            # Rodar apenas entre 08:00 e 19:00
            if 8 <= now.hour <= 19:
                db = SessionLocal()
                await process_financial_notifications(db)
                db.close()
            
        except Exception as e:
            print(f"[FinancialBot] Erro no loop: {e}")
            
        await asyncio.sleep(2700)


@app.on_event("startup")
async def startup_event():
    # Iniciar loop em background
    asyncio.create_task(director_notification_loop())
    asyncio.create_task(financial_notification_loop())
    import requests
    from app.services.whatsapp import ZAPI_CLIENT_TOKEN
    try:
        url = f"{ZAPI_BASE_URL}/status"
        headers = {
            "Client-Token": ZAPI_CLIENT_TOKEN
        }
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        return {"conectado": True, "status": data}
    except Exception as e:
        return {"conectado": False, "erro": str(e)}