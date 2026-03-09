from fastapi import Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from jinja2 import Environment, FileSystemLoader, select_autoescape
from app.core.database import get_db, SessionLocal
from app.models import User
from app.core.helpers import format_money

# --- Templating ---
env = Environment(
    loader=FileSystemLoader("app/templates"),
    autoescape=select_autoescape(["html", "xml"]),
    auto_reload=True
)
env.filters["brl"] = format_money
env.globals["get_flashed_messages"] = lambda: []
env.globals["APP_VERSION"] = "4.0"

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

# --- Auth ---
def require_login(request: Request, db: Session) -> User:
    uid = request.session.get("uid")
    if not uid:
        raise HTTPException(status_code=401, detail="Not logged in")
    user = db.get(User, uid)
    if not user or not user.active:
        raise HTTPException(status_code=401, detail="Invalid user")
    return user
