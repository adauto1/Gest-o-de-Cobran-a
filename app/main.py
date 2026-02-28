from __future__ import annotations
import os
import logging
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_302_FOUND
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.database import Base, engine, get_db, run_migrations
from app.models import User, Configuracoes
from app.core.security import hash_password
from app.core.web import render
from app.core.config import settings
from app.services.notifications import run_director_alerts, run_financial_alerts
from app.scheduler import run_collection_check, check_unfulfilled_promises, save_aging_snapshot, run_weekly_report

# --- Routers ---
from app.api.routers import (
    customers, queue, rules, import_data, auth, users, actions, messages, dashboard, commissions, settings, conferencia,
    campanhas, acordos, promessas, relatorio, whatsapp_webhook
)

# --- Logging Estruturado ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Initialize Database
Base.metadata.create_all(bind=engine)
run_migrations(engine)

# APScheduler global (acessado pelo settings router para reagendar)
scheduler = AsyncIOScheduler(timezone="America/Campo_Grande")

app = FastAPI(title="Gestor de Cobrança — Portal Móveis")

# --- Security Headers Middleware ---
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' cdn.jsdelivr.net unpkg.com; "
            "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
            "img-src 'self' data: blob:; "
            "font-src 'self' cdn.jsdelivr.net; "
            "connect-src 'self';"
        )
        return response

app.add_middleware(SecurityHeadersMiddleware)

# Middleware
SECRET_KEY = settings.session_secret
if SECRET_KEY == "CHANGE-ME-IN-PROD":
    logger.warning(
        "[SEGURANÇA] SESSION_SECRET usando valor padrão inseguro! "
        "Defina a variável de ambiente SESSION_SECRET em produção."
    )
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Static Files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Registered Routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(customers.router)
app.include_router(queue.router)
app.include_router(rules.router)
app.include_router(import_data.router)
app.include_router(actions.router)
app.include_router(messages.router)
app.include_router(dashboard.router)
app.include_router(commissions.router)
app.include_router(settings.router)
app.include_router(conferencia.router)
app.include_router(campanhas.router)
app.include_router(acordos.router)
app.include_router(promessas.router)
app.include_router(relatorio.router)
app.include_router(whatsapp_webhook.router)

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        return RedirectResponse("/login")
    return await request.app.default_exception_handler(request, exc)

@app.get("/")
def root_redirect():
    return RedirectResponse("/dashboard")

@app.on_event("startup")
async def startup_event():
    # Admin Auto-creation
    db = next(get_db())
    admin_email = settings.default_admin_email
    admin = db.query(User).filter(User.email == admin_email).first()
    if not admin:
        admin_pass = settings.default_admin_password
        db.add(User(
            name="Administrador",
            email=admin_email,
            password_hash=hash_password(admin_pass),
            role="ADMIN",
            active=True
        ))
        db.commit()
        logger.info(f"[SISTEMA] Usuario admin criado: {admin_email}")

    # Buscar hora configurada para a regua de cobranca
    config = db.query(Configuracoes).first()
    hora_disparo = getattr(config, 'scheduler_hora_disparo', 9) if config else 9
    db.close()

    from app.core.database import SessionLocal as SL

    # Job 1: Regua de cobranca — hora configuravel (padrao 9h)
    scheduler.add_job(
        lambda: run_collection_check(SL),
        CronTrigger(hour=hora_disparo, minute=0),
        id="collection_check",
        replace_existing=True
    )

    # Job 2: Alertas de diretores — a cada 1h (primeira execução em 1h, não no startup)
    scheduler.add_job(
        run_director_alerts,
        "interval",
        hours=1,
        id="director_alerts",
        replace_existing=True,
        next_run_time=datetime.now(scheduler.timezone) + timedelta(hours=1)
    )

    # Job 3: Alertas financeiros — a cada 45min (primeira execução em 45min, não no startup)
    scheduler.add_job(
        run_financial_alerts,
        "interval",
        minutes=45,
        id="financial_alerts",
        replace_existing=True,
        next_run_time=datetime.now(scheduler.timezone) + timedelta(minutes=45)
    )

    # Job 4: Promessas não cumpridas — diário às 8h
    scheduler.add_job(
        lambda: check_unfulfilled_promises(SL),
        CronTrigger(hour=8, minute=0),
        id="check_promises",
        replace_existing=True
    )

    # Job 5: Snapshot de aging — diário às 10h
    scheduler.add_job(
        lambda: save_aging_snapshot(SL),
        CronTrigger(hour=10, minute=0),
        id="aging_snapshot",
        replace_existing=True
    )

    # Job 6: Relatório semanal — sábados às 18h
    scheduler.add_job(
        lambda: run_weekly_report(SL),
        CronTrigger(day_of_week="sat", hour=18, minute=0),
        id="weekly_report",
        replace_existing=True
    )

    scheduler.start()
    logger.info(f"[SCHEDULER] Jobs registrados. Regua dispara as {hora_disparo}h.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
